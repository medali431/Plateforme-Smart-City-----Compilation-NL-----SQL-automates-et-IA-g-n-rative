import pytest
from src.nl_compiler import compile_query, SyntaxError


@pytest.mark.parametrize(
    ("query", "fragment"),
    [
        ("Affiche les 5 zones les plus polluées", "GROUP BY"),
        ("Combien de capteurs sont hors service ?", "HORS_SERVICE"),
        ("Quels citoyens ont un score écologique > 80 ?", "score_ecolo"),
        ("Donne-moi le trajet le plus économique en CO2", "trajets"),
        ("Quelles interventions sont en cours ?", "statut != 'TERMINE'"),
    ],
)
def test_supported_queries(query, fragment):
    ast, sql = compile_query(query)
    assert ast is not None
    assert fragment.lower() in sql.lower()


def test_unknown_query():
    with pytest.raises(SyntaxError):
        compile_query("Raconte-moi une blague")
