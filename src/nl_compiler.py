from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LexicalError(Exception):
    pass


class SyntaxError(Exception):
    pass


class SemanticError(Exception):
    pass


class TokenType(Enum):
    WORD = "WORD"
    NUMBER = "NUMBER"
    OPERATOR = "OPERATOR"
    QUESTION = "QUESTION"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenType
    value: str


@dataclass
class ASTNode:
    operation: str
    table: Optional[str] = None
    columns: tuple[str, ...] = ()
    where: Optional[tuple[str, str, object]] = None
    group_by: Optional[str] = None
    order_by: Optional[str] = None
    direction: str = "ASC"
    limit: Optional[int] = None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^\w\s><=*-]", " ", text)


def lexer(text: str) -> list[Token]:
    text = normalize(text)
    tokens: list[Token] = []
    for match in re.finditer(r"\d+|>=|<=|>|<|=|\*|[a-z0-9_-]+", text):
        value = match.group()
        if value.isdigit():
            tokens.append(Token(TokenType.NUMBER, value))
        elif value in ("<", ">", "<=", ">=", "="):
            tokens.append(Token(TokenType.OPERATOR, value))
        else:
            tokens.append(Token(TokenType.WORD, value))
    if not tokens:
        raise LexicalError("La requête ne contient aucun mot reconnu.")
    tokens.append(Token(TokenType.EOF, ""))
    return tokens


class NLQueryParser:
    def parse(self, query: str) -> ASTNode:
        text = normalize(query)

        if "zones" in text and ("polluees" in text or "polluees" in text or "pollution" in text):
            limit_match = re.search(r"\b(\d+)\b", text)
            limit = int(limit_match.group(1)) if limit_match else 5
            if "moins" in text:
                direction = "ASC"
            else:
                direction = "DESC"
            return ASTNode(
                operation="GROUP",
                table="mesures",
                columns=("zone", "avg_pollution"),
                group_by="zone",
                order_by="avg_pollution",
                direction=direction,
                limit=limit,
            )

        if ("combien" in text or "nombre" in text) and "capteurs" in text:
            status = None
            if "hors service" in text or "hors_service" in text:
                status = "HORS_SERVICE"
            elif "actifs" in text or "actif" in text:
                status = "ACTIF"
            elif "signales" in text:
                status = "SIGNALE"
            elif "maintenance" in text:
                status = "EN_MAINTENANCE"
            return ASTNode("COUNT", "capteurs", ("count",), ("statut", "=", status) if status else None)

        if "citoyens" in text and "score" in text:
            number = re.search(r"\b(\d+)\b", text)
            threshold = int(number.group(1)) if number else 80
            direction = "<" if "inférieur" in text or "moins de" in text else ">"
            return ASTNode(
                "SELECT",
                "citoyens",
                ("nom", "score_ecolo"),
                ("score_ecolo", direction, threshold),
                order_by="score_ecolo",
                direction="DESC",
            )

        if "traject" in text or "trajets" in text or "trajet" in text:
            return ASTNode(
                "SELECT",
                "trajets",
                ("trajet_id", "economie_co2"),
                order_by="economie_co2",
                direction="DESC",
                limit=1,
            )

        if "interventions" in text or "intervention" in text:
            status = None
            if "cours" in text or "en cours" in text:
                status = "EN_COURS"
            elif "terminees" in text or "terminees" in text:
                status = "TERMINE"
            if status == "EN_COURS":
                return ASTNode(
                    "SELECT", "interventions",
                    ("intervention_id", "statut", "description", "priorite", "demande_at"),
                    ("statut", "!=", "TERMINE"),
                    order_by="demande_at",
                    direction="DESC",
                )
            if status:
                return ASTNode(
                    "SELECT", "interventions",
                    ("intervention_id", "statut", "description", "priorite", "demande_at"),
                    ("statut", "=", status),
                )
            return ASTNode(
                "SELECT", "interventions",
                ("intervention_id", "statut", "description", "priorite", "demande_at"),
                order_by="demande_at",
                direction="DESC",
            )

        if "mesures" in text or "mesure" in text:
            limit_match = re.search(r"\b(\d+)\b", text)
            limit = int(limit_match.group(1)) if limit_match else 20
            return ASTNode(
                "SELECT", "mesures",
                ("mesure_id", "zone_id", "type_mesure", "valeur", "unite", "mesure_at"),
                order_by="mesure_at",
                direction="DESC",
                limit=limit,
            )

        raise SyntaxError(
            "Je ne reconnais pas cette intention. Exemples: "
            "'Affiche les 5 zones les plus polluées', "
            "'Combien de capteurs sont hors service ?', "
            "'Quels citoyens ont un score écologique > 80 ?', "
            "'Quelles interventions sont en cours ?'"
        )


def ast_to_sql(ast: ASTNode) -> str:
    if ast.operation == "COUNT":
        sql = f"SELECT COUNT(*) AS nombre FROM {ast.table}"
        if ast.where:
            column, op, value = ast.where
            if value is not None:
                sql += f" WHERE {column} = '{value}'"
        return sql

    if ast.operation == "GROUP":
        return (
            "SELECT z.nom AS zone, ROUND(AVG(m.valeur), 2) AS avg_pollution "
            "FROM mesures m JOIN zones z ON z.zone_id = m.zone_id "
            "GROUP BY z.nom ORDER BY avg_pollution DESC "
            f"LIMIT {ast.limit or 5}"
        )

    if ast.table == "citoyens":
        columns = ", ".join(ast.columns)
        column, op, value = ast.where
        return f"SELECT {columns} FROM citoyens WHERE {column} {op} {value} ORDER BY score_ecolo DESC"

    if ast.table == "trajets":
        return (
            "SELECT trajet_id, economie_co2 FROM trajets "
            "ORDER BY economie_co2 DESC LIMIT 1"
        )

    if ast.table == "interventions":
        columns = ", ".join(ast.columns)
        sql = f"SELECT {columns} FROM interventions"
        if ast.where:
            column, op, value = ast.where
            if value == "EN_COURS":
                sql += " WHERE statut != 'TERMINE'"
            else:
                sql += f" WHERE {column} {op} '{value}'"
        if ast.order_by:
            sql += f" ORDER BY {ast.order_by} {ast.direction}"
        return sql

    if ast.table == "mesures":
        columns = ", ".join(ast.columns)
        sql = f"SELECT {columns} FROM mesures"
        if ast.order_by:
            sql += f" ORDER BY {ast.order_by} {ast.direction}"
        if ast.limit:
            sql += f" LIMIT {ast.limit}"
        return sql

    raise SemanticError("Cette opération n'est pas prise en charge.")


def compile_query(query: str) -> tuple[ASTNode, str]:
    lexer(query)
    ast = NLQueryParser().parse(query)
    return ast, ast_to_sql(ast)

