from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def database_path_from_url(database_url: str) -> Path:
    """Resolve the supported SQLite DATABASE_URL to a local database file."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(
            "Cette fonction résout uniquement SQLite. DATABASE_URL doit être au format "
            "'sqlite:///chemin/vers/base.db'."
        )

    raw_path = database_url[len(prefix):]
    if not raw_path or raw_path == ":memory:":
        raise ValueError("DATABASE_URL doit désigner un fichier SQLite persistant.")

    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/smart_city.db").strip()
IS_POSTGRESQL = DATABASE_URL.startswith(("postgresql://", "postgres://"))
DB_PATH = database_path_from_url(DATABASE_URL) if not IS_POSTGRESQL else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS zones (
    zone_id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL UNIQUE,
    secteur TEXT NOT NULL,
    superficie_km2 REAL CHECK (superficie_km2 > 0)
);

CREATE TABLE IF NOT EXISTS citoyens (
    citoyen_id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT UNIQUE,
    score_ecolo INTEGER CHECK (score_ecolo BETWEEN 0 AND 100),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS techniciens (
    technicien_id INTEGER PRIMARY KEY,
    nom TEXT NOT NULL,
    specialite TEXT NOT NULL,
    disponible BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS capteurs (
    capteur_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    statut TEXT NOT NULL CHECK (statut IN ('INACTIF','ACTIF','SIGNALE','EN_MAINTENANCE','HORS_SERVICE')),
    taux_erreur REAL CHECK (taux_erreur >= 0),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    installe_at TEXT,
    hors_service_at TEXT
);

CREATE TABLE IF NOT EXISTS interventions (
    intervention_id INTEGER PRIMARY KEY,
    demande_at TEXT NOT NULL,
    statut TEXT NOT NULL CHECK (statut IN ('DEMANDE','TECH1_ASSigne','TECH2_VALIDE','IA_VALIDE','TERMINE')),
    description TEXT NOT NULL,
    priorite TEXT CHECK (priorite IN ('basse','moyenne','haute','critique')),
    capteur_id TEXT REFERENCES capteurs(capteur_id),
    zone_id INTEGER REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS intervention_assignments (
    intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id),
    technicien_id INTEGER NOT NULL REFERENCES techniciens(technicien_id),
    role TEXT NOT NULL,
    PRIMARY KEY (intervention_id, technicien_id)
);

CREATE TABLE IF NOT EXISTS vehicules (
    vehicule_id TEXT PRIMARY KEY,
    modele TEXT NOT NULL,
    statut TEXT NOT NULL CHECK (statut IN ('STATIONNE','EN_ROUTE','EN_PANNE','ARRIVE'))
);

CREATE TABLE IF NOT EXISTS trajets (
    trajet_id INTEGER PRIMARY KEY,
    vehicule_id TEXT NOT NULL REFERENCES vehicules(vehicule_id),
    origine TEXT NOT NULL,
    destination TEXT NOT NULL,
    debut_at TEXT NOT NULL,
    fin_at TEXT,
    distance_km REAL,
    economie_co2 REAL
);

CREATE TABLE IF NOT EXISTS mesures (
    mesure_id INTEGER PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    capteur_id TEXT REFERENCES capteurs(capteur_id),
    type_mesure TEXT NOT NULL,
    valeur REAL NOT NULL,
    unite TEXT NOT NULL,
    mesure_at TEXT NOT NULL
);
"""


class PostgreSQLConnection:
    """Small DB-API adapter used to share the app's connection interface."""

    dialect = "postgresql"

    def __init__(self, connection: Any):
        self._connection = connection

    @staticmethod
    def _convert_placeholders(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql: str, params=None):
        cursor = self._connection.cursor()
        cursor.execute(self._convert_placeholders(sql), params)
        return cursor

    def executemany(self, sql: str, params):
        cursor = self._connection.cursor()
        cursor.executemany(self._convert_placeholders(sql), params)
        return cursor

    def executescript(self, script: str):
        cursor = self._connection.cursor()
        for statement in script.split(";"):
            statement = "\n".join(
                line for line in statement.splitlines()
                if not line.lstrip().startswith("--")
            ).strip()
            if statement:
                cursor.execute(statement)
        return cursor

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def get_connection():
    if IS_POSTGRESQL:
        try:
            import psycopg2
            from psycopg2.extras import DictCursor
        except ImportError as exc:
            raise RuntimeError(
                "Le pilote PostgreSQL manque. Installez les dépendances avec "
                "'python -m pip install -r requirements.txt'."
            ) from exc
        try:
            connection = psycopg2.connect(
                DATABASE_URL,
                connect_timeout=5,
                cursor_factory=DictCursor,
            )
        except psycopg2.Error as exc:
            raise RuntimeError(
                "Connexion PostgreSQL impossible. Vérifiez DATABASE_URL, "
                "le serveur PostgreSQL et les identifiants dans .env."
            ) from exc
        return PostgreSQLConnection(connection)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(seed: bool = True):
    with get_connection() as conn:
        if IS_POSTGRESQL:
            postgres_schema = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
            conn.executescript(postgres_schema)
        else:
            conn.executescript(SCHEMA)
        if seed:
            count = conn.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
            if count == 0:
                seed_database(conn)
    return "PostgreSQL" if IS_POSTGRESQL else str(DB_PATH)


def seed_database(conn):
    random.seed(2030)
    zones = [
        ("Centre-ville", "Nord", 4.2),
        ("Medina", "Centre", 2.8),
        ("Hamada", "Sud", 8.1),
        ("Khezama", "Est", 5.6),
        ("Khzema Ouest", "Ouest", 6.3),
        ("Gammarth", "Nord", 7.4),
        ("Zaouiet", "Sud", 3.9),
    ]
    conn.executemany(
        "INSERT INTO zones(nom, secteur, superficie_km2) VALUES (?, ?, ?)",
        zones,
    )

    first_names = ["Ahmed", "Ines", "Mariem", "Youssef", "Nour", "Omar", "Salma", "Rania"]
    last_names = ["Ben Ali", "Trabelsi", "Ayari", "Khaldi", "Mansour", "Jaziri", "Sassi"]
    for i in range(1, 201):
        zone_id = ((i - 1) % len(zones)) + 1
        prenom = random.choice(first_names)
        nom = random.choice(last_names)
        score = random.randint(25, 98)
        conn.execute(
            "INSERT INTO citoyens(nom, prenom, email, score_ecolo, zone_id) VALUES (?, ?, ?, ?, ?)",
            (nom, prenom, f"{prenom.lower()}.{i}@neossoussa.tn", score, zone_id),
        )

    for i, (nom, specialite) in enumerate([
        ("Ali Haddad", "électricité"), ("Leila Mejri", "capteurs air"),
        ("Mohamed Dridi", "réseau"), ("Syrine Bensalem", "maintenance"),
    ], 1):
        conn.execute(
            "INSERT INTO techniciens(nom, specialite, disponible) VALUES (?, ?, ?)",
            (nom, specialite, i % 3 != 0),
        )

    sensor_statuses = ["ACTIF", "ACTIF", "ACTIF", "SIGNALE", "EN_MAINTENANCE", "HORS_SERVICE"]
    sensor_types = ["qualité air", "bruit", "trafic", "température", "pollution"]
    now = datetime(2026, 3, 15, 12, 0)
    for i in range(1, 61):
        zone_id = ((i - 1) % len(zones)) + 1
        status = random.choice(sensor_statuses)
        error = random.uniform(1, 18) if status != "ACTIF" else random.uniform(0.2, 7)
        outage = (now - timedelta(hours=random.randint(25, 180))).isoformat() if status == "HORS_SERVICE" else None
        conn.execute(
            """INSERT INTO capteurs
            (capteur_id, type, statut, taux_erreur, zone_id, installe_at, hors_service_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"C-{400+i}", random.choice(sensor_types), status, round(error, 2), zone_id,
             (now - timedelta(days=random.randint(30, 800))).isoformat(), outage),
        )

    intervention_statuses = ["DEMANDE", "TECH1_ASSigne", "TECH2_VALIDE", "IA_VALIDE", "TERMINE"]
    for i in range(1, 81):
        zone_id = ((i - 1) % len(zones)) + 1
        sensor_id = f"C-{400 + ((i - 1) % 60) + 1}"
        status = random.choice(intervention_statuses)
        priority = random.choice(["basse", "moyenne", "haute", "critique"])
        conn.execute(
            """INSERT INTO interventions
            (intervention_id, demande_at, statut, description, priorite, capteur_id, zone_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, (now - timedelta(hours=random.randint(1, 720))).isoformat(),
             status, f"Diagnostic et maintenance du capteur {sensor_id}", priority, sensor_id, zone_id),
        )
        if status not in ("DEMANDE", "TERMINE"):
            conn.execute(
                """INSERT INTO intervention_assignments
                VALUES (?, ?, 'technicien_principal') ON CONFLICT DO NOTHING""",
                (i, ((i - 1) % 4) + 1),
            )

    for i in range(1, 31):
        conn.execute(
            "INSERT INTO vehicules(vehicule_id, modele, statut) VALUES (?, ?, ?)",
            (f"V-{i:03}", random.choice(["NeoBus X1", "EcoRide 7", "VoltaVan"]),
             random.choice(["STATIONNE", "EN_ROUTE", "EN_PANNE", "ARRIVE"])),
        )
        conn.execute(
            """INSERT INTO trajets
            (vehicule_id, origine, destination, debut_at, fin_at, distance_km, economie_co2)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"V-{i:03}", "Station centrale", random.choice(["Centre-ville", "Medina", "Hamada"]),
             (now - timedelta(hours=random.randint(1, 100))).isoformat(),
             now.isoformat(), round(random.uniform(3, 28), 1), round(random.uniform(1, 22), 2)),
        )

    for i in range(1, 1501):
        zone_id = ((i - 1) % len(zones)) + 1
        sensor_id = f"C-{400 + ((i - 1) % 60) + 1}"
        pollution = random.gauss(52 + zone_id * 4, 18)
        if i % 19 == 0:
            pollution += 55
        measured_at = now - timedelta(minutes=30 * (1500 - i))
        conn.execute(
            """INSERT INTO mesures(zone_id, capteur_id, type_mesure, valeur, unite, mesure_at)
            VALUES (?, ?, 'pollution', ?, 'µg/m3', ?)""",
            (zone_id, sensor_id, round(max(8, pollution), 2), measured_at.isoformat()),
        )
    conn.commit()
