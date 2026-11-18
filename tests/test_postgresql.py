import pytest

from src.database import PostgreSQLConnection
from src.llm_sql import UnsafeQueryError, _validate_postgresql_query
from src.ai_report import generate_report


class FakeResult:
    description = []

    def __init__(self, rows=()):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_postgresql_adapter_converts_placeholders():
    raw_connection = FakeConnection()
    connection = PostgreSQLConnection(raw_connection)

    connection.execute("SELECT * FROM capteurs WHERE statut = ?", ("ACTIF",))

    assert raw_connection.cursor_instance.calls == [
        ("SELECT * FROM capteurs WHERE statut = %s", ("ACTIF",))
    ]


def test_report_uses_postgresql_date_filter(monkeypatch):
    class ReportConnection:
        dialect = "postgresql"

        def __init__(self):
            self.calls = []

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            if "FROM mesures" in sql:
                return FakeResult()
            return FakeResult([{"n": 0}])

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    connection = ReportConnection()
    generate_report(connection, "2026-03-15")

    assert "::date = %s::date" in connection.calls[0][0]
    assert connection.calls[0][1] == ("2026-03-15",)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT statut, COUNT(*) FROM capteurs GROUP BY statut",
        "WITH actifs AS (SELECT * FROM capteurs WHERE statut = 'ACTIF') "
        "SELECT COUNT(*) FROM actifs",
    ],
)
def test_postgresql_readonly_validator_allows_city_queries(sql):
    _validate_postgresql_query(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM capteurs",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT pg_read_file('/etc/passwd') FROM capteurs",
        "SELECT * FROM capteurs; DROP TABLE zones",
    ],
)
def test_postgresql_readonly_validator_rejects_unsafe_queries(sql):
    with pytest.raises(UnsafeQueryError):
        _validate_postgresql_query(sql)
