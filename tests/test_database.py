from src.database import init_database, get_connection
from src.database import BASE_DIR, database_path_from_url


def test_database_seed_is_large_enough():
    init_database(seed=True)
    with get_connection() as conn:
        zones = conn.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
        citizens = conn.execute("SELECT COUNT(*) FROM citoyens").fetchone()[0]
        measurements = conn.execute("SELECT COUNT(*) FROM mesures").fetchone()[0]
    assert zones >= 5
    assert citizens >= 100
    assert measurements >= 1000


def test_database_url_resolves_relative_sqlite_path():
    assert database_path_from_url("sqlite:///data/neossousse.db") == (
        BASE_DIR / "data" / "neossousse.db"
    ).resolve()


def test_database_url_rejects_unsupported_database():
    import pytest

    with pytest.raises(ValueError, match="uniquement SQLite"):
        database_path_from_url("postgresql://localhost/neossousse")
