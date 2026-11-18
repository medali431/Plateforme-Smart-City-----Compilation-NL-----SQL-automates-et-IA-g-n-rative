from types import SimpleNamespace

import pytest

from src.database import get_connection, init_database
from src.llm_sql import (
    LLMConfigurationError,
    UnsafeQueryError,
    execute_readonly_query,
    generate_sql,
)


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
        generate_sql("Affiche les capteurs")


def test_question_is_sent_to_llm_and_sql_is_returned(monkeypatch):
    class FakeOpenAI:
        def __init__(self, api_key, base_url):
            assert api_key == "test-key"
            assert base_url == "https://api.groq.com/openai/v1"
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self.create_completion)
            )

        @staticmethod
        def create_completion(**kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            assert "question" in kwargs["messages"][1]["content"].lower()
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"sql":"SELECT COUNT(*) FROM capteurs"}'
                        )
                    )
                ]
            )

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    assert generate_sql("Combien de capteurs ?") == "SELECT COUNT(*) FROM capteurs"


def test_readonly_query_runs_against_city_tables():
    init_database(seed=True)
    with get_connection() as conn:
        result, truncated = execute_readonly_query(
            conn,
            "SELECT statut, COUNT(*) AS nombre FROM capteurs GROUP BY statut",
        )
    assert "statut" in result.columns
    assert len(result) > 0
    assert truncated is False


def test_readonly_query_supports_common_text_filters():
    init_database(seed=True)
    with get_connection() as conn:
        result, _ = execute_readonly_query(
            conn,
            "SELECT capteur_id FROM capteurs WHERE statut LIKE '%ACTIF%' LIMIT 5",
        )
    assert len(result) > 0


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM capteurs",
        "SELECT name FROM sqlite_master",
        "SELECT load_extension('example') FROM capteurs LIMIT 1",
        "SELECT 1",
    ],
)
def test_unsafe_queries_are_rejected(sql):
    init_database(seed=True)
    with get_connection() as conn:
        with pytest.raises(UnsafeQueryError):
            execute_readonly_query(conn, sql)
        count = conn.execute("SELECT COUNT(*) FROM capteurs").fetchone()[0]
    assert count > 0
