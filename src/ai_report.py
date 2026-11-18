from __future__ import annotations

import os


def generate_report(conn, date: str = "2026-03-15") -> dict[str, str]:
    """Rapport déterministe local, avec complément OpenAI optionnel."""
    date_filter = (
        "m.mesure_at::date = %s::date"
        if getattr(conn, "dialect", "") == "postgresql"
        else "substr(m.mesure_at, 1, 10) = ?"
    )
    zones = conn.execute(
        f"""
        SELECT z.nom, ROUND(AVG(m.valeur), 1) AS moyenne
        FROM mesures m JOIN zones z ON z.zone_id = m.zone_id
        WHERE {date_filter}
        GROUP BY z.nom ORDER BY moyenne DESC
        """,
        (date,),
    ).fetchall()
    out_of_service = conn.execute(
        "SELECT COUNT(*) AS n FROM capteurs WHERE statut = 'HORS_SERVICE'"
    ).fetchone()["n"]
    interventions = conn.execute(
        "SELECT COUNT(*) AS n FROM interventions WHERE statut != 'TERMINE'"
    ).fetchone()["n"]

    threshold = 80
    polluted = [row for row in zones if row["moyenne"] >= threshold]
    top = zones[0] if zones else None
    summary = (
        f"Rapport qualité de l'air du {date} : "
        f"{len(polluted)} zone(s) dépassent le seuil de {threshold} µg/m3."
    )
    if top:
        summary += f" La zone la plus polluée est {top['nom']} avec {top['moyenne']} µg/m3."

    actions = [
        f"Surveiller les {out_of_service} capteurs actuellement hors service.",
        f"Prioriser les {interventions} interventions encore ouvertes.",
    ]
    if polluted:
        actions.insert(0, f"Déployer une intervention environnementale dans {polluted[0]['nom']}.")

    text = summary + "\n\nActions recommandées :\n- " + "\n- ".join(actions)

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "Tu es un analyste urbain francophone. Produis un rapport concis."},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            text = response.choices[0].message.content or text
        except Exception:
            pass

    return {
        "title": f"Rapport Neo-Sousse - {date}",
        "summary": summary,
        "text": text,
        "actions": "\n".join(f"- {action}" for action in actions),
    }
