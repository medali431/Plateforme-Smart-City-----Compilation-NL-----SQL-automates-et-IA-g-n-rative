from __future__ import annotations

import json
import os
import sqlite3
import time

import pandas as pd
import sqlglot
from sqlglot import exp

from src.database import IS_POSTGRESQL


class LLMConfigurationError(Exception):
    """The LLM provider is not configured."""


class LLMGenerationError(Exception):
    """The LLM could not produce a usable SQL query."""


class UnsafeQueryError(Exception):
    """The generated SQL is not an allowed read-only query."""


SCHEMA_DESCRIPTION = """
Tables and columns available:
- zones(zone_id, nom, secteur, superficie_km2)
- citoyens(citoyen_id, nom, prenom, email, score_ecolo, zone_id)
- techniciens(technicien_id, nom, specialite, disponible)
- capteurs(capteur_id, type, statut, taux_erreur, zone_id, installe_at, hors_service_at)
- interventions(intervention_id, demande_at, statut, description, priorite, capteur_id, zone_id)
- intervention_assignments(intervention_id, technicien_id, role)
- vehicules(vehicule_id, modele, statut)
- trajets(trajet_id, vehicule_id, origine, destination, debut_at, fin_at, distance_km, economie_co2)
- mesures(mesure_id, zone_id, capteur_id, type_mesure, valeur, unite, mesure_at)

Useful facts:
- Pollution readings are in mesures where type_mesure='pollution' and valeur is in µg/m3.
- Join mesures.zone_id to zones.zone_id to show zone names.
- Current sensor statuses: INACTIF, ACTIF, SIGNALE, EN_MAINTENANCE, HORS_SERVICE.
- Current intervention statuses: DEMANDE, TECH1_ASSigne, TECH2_VALIDE, IA_VALIDE, TERMINE.
- A vehicle can be STATIONNE, EN_ROUTE, EN_PANNE or ARRIVE.
- Dates are ISO-8601 text or PostgreSQL timestamps.
"""

SAFE_TABLES = {
    "zones",
    "citoyens",
    "techniciens",
    "capteurs",
    "interventions",
    "intervention_assignments",
    "vehicules",
    "trajets",
    "mesures",
}

SAFE_FUNCTIONS = {
    "abs",
    "avg",
    "coalesce",
    "count",
    "date",
    "datetime",
    "ifnull",
    "instr",
    "length",
    "like",
    "lower",
    "max",
    "min",
    "nullif",
    "round",
    "replace",
    "strftime",
    "substr",
    "sum",
    "time",
    "total",
    "trim",
    "upper",
    "cast",
    "extract",
    "date_trunc",
    "concat",
    "concat_ws",
}


def generate_sql(question: str) -> str:
    question = question.strip()
    if not question:
        raise LLMGenerationError("Saisissez une question avant de lancer la génération.")

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise LLMConfigurationError(
            "La clé Groq est absente. Créez une clé sur https://console.groq.com/keys, "
            "ajoutez GROQ_API_KEY dans le fichier .env, puis redémarrez l'application."
        )

    try:
        from openai import OpenAI, OpenAIError
    except ImportError as exc:
        raise LLMConfigurationError(
            "Le client API n'est pas installé. Exécutez : pip install -r requirements.txt"
        ) from exc

    model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
    model = model or "qwen/qwen3.8-27b"
    dialect = "PostgreSQL" if IS_POSTGRESQL else "SQLite"
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Tu convertis une question utilisateur en une seule requête SQL {dialect} "
                        "en lecture seule. Réponds uniquement en JSON valide au format "
                        '{"sql":"SELECT ..."} . Utilise exclusivement les tables et colonnes '
                        "du schéma fourni. Ne produis jamais INSERT, UPDATE, DELETE, DDL, "
                        "PRAGMA, commentaires SQL ou plusieurs instructions. Si la question "
                        "n'est pas liée au schéma, retourne {\"sql\":\"\"}."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Schéma:\n{SCHEMA_DESCRIPTION}\nQuestion:\n{question}",
                },
            ],
        )
    except OpenAIError as exc:
        raise LLMGenerationError(f"Échec de l'appel au service Groq : {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content:
        raise LLMGenerationError("Le modèle n'a retourné aucune requête.")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMGenerationError("La réponse du modèle n'est pas un JSON valide.") from exc

    sql = payload.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise LLMGenerationError(
            "Le modèle n'a pas pu transformer cette question en requête sur les données disponibles."
        )
    if len(sql) > 10_000:
        raise LLMGenerationError("La requête générée dépasse la taille maximale autorisée.")
    return sql.strip()


def execute_readonly_query(conn: sqlite3.Connection, sql: str) -> tuple[pd.DataFrame, bool]:
    """Execute one bounded SELECT, denying writes, unsafe tables and unsafe functions."""
    statement = sql.strip()
    if not statement:
        raise UnsafeQueryError("La requête SQL est vide.")

    if getattr(conn, "dialect", "") == "postgresql":
        _validate_postgresql_query(statement)
        try:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '5000ms'")
            cursor = conn.execute(statement)
            if cursor.description is None:
                raise UnsafeQueryError("Seules les requêtes de lecture sont autorisées.")
            rows = cursor.fetchmany(501)
            columns = [column[0] for column in cursor.description]
            truncated = len(rows) > 500
            return pd.DataFrame.from_records(
                [tuple(row) for row in rows[:500]],
                columns=columns,
            ), truncated
        except UnsafeQueryError:
            raise
        except Exception as exc:
            conn.rollback()
            message = str(exc).splitlines()[0]
            raise UnsafeQueryError(f"PostgreSQL a refusé la requête : {message}") from exc
        finally:
            conn.rollback()

    def authorize(action, arg1, arg2, database, trigger):
        if action in (sqlite3.SQLITE_SELECT,):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            return (
                sqlite3.SQLITE_OK
                if arg1 and arg1.lower() in SAFE_TABLES
                else sqlite3.SQLITE_DENY
            )
        if action == sqlite3.SQLITE_FUNCTION:
            function_name = (arg2 or arg1 or "").lower()
            return (
                sqlite3.SQLITE_OK
                if function_name in SAFE_FUNCTIONS
                else sqlite3.SQLITE_DENY
            )
        return sqlite3.SQLITE_DENY

    deadline = time.monotonic() + 5
    read_tables: set[str] = set()

    def authorize_query(action, arg1, arg2, database, trigger):
        if action == sqlite3.SQLITE_READ and arg1:
            read_tables.add(arg1.lower())
        return authorize(action, arg1, arg2, database, trigger)

    def stop_expensive_query():
        return int(time.monotonic() > deadline)

    try:
        conn.execute("PRAGMA query_only=ON")
        conn.set_authorizer(authorize_query)
        conn.set_progress_handler(stop_expensive_query, 1000)
        cursor = conn.execute(statement)
        if cursor.description is None:
            raise UnsafeQueryError("Seules les requêtes SELECT sont autorisées.")
        if not read_tables:
            raise UnsafeQueryError("La requête doit lire au moins une table Smart City.")
        rows = cursor.fetchmany(501)
        columns = [column[0] for column in cursor.description]
        truncated = len(rows) > 500
        frame = pd.DataFrame.from_records(
            [tuple(row) for row in rows[:500]],
            columns=columns,
        )
        return frame, truncated
    except sqlite3.DatabaseError as exc:
        if "not authorized" in str(exc).lower():
            raise UnsafeQueryError(
                "La requête a été bloquée : seules les lectures des tables Smart City "
                "et les fonctions SQL autorisées sont permises."
            ) from exc
        if "interrupted" in str(exc).lower():
            raise UnsafeQueryError("La requête a dépassé la limite de calcul autorisée.") from exc
        raise UnsafeQueryError(f"SQLite a refusé la requête : {exc}") from exc
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)
        conn.execute("PRAGMA query_only=OFF")


def _validate_postgresql_query(statement: str) -> None:
    try:
        parsed = sqlglot.parse(statement, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeQueryError("La requête SQL générée n'est pas valide pour PostgreSQL.") from exc

    if len(parsed) != 1 or not isinstance(parsed[0], exp.Query):
        raise UnsafeQueryError("Une seule requête SELECT est autorisée.")

    query = parsed[0]
    cte_names = {
        cte.alias_or_name.lower()
        for cte in query.find_all(exp.CTE)
    }
    found_tables = set()
    for table in query.find_all(exp.Table):
        name = table.name.lower()
        if table.db or table.catalog or (name not in SAFE_TABLES and name not in cte_names):
            raise UnsafeQueryError("La requête utilise une table non autorisée.")
        if name in SAFE_TABLES:
            found_tables.add(name)
    if not found_tables:
        raise UnsafeQueryError("La requête doit lire au moins une table Smart City.")

    for function in query.find_all(exp.Func):
        name = (
            function.name if isinstance(function, exp.Anonymous)
            else function.sql_name()
        ).lower()
        if name not in SAFE_FUNCTIONS:
            raise UnsafeQueryError(f"La fonction SQL '{name}' n'est pas autorisée.")
