import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(Path(__file__).resolve().parent / ".env")

from src.database import get_connection, init_database
from src.llm_sql import (
    LLMConfigurationError,
    LLMGenerationError,
    UnsafeQueryError,
    execute_readonly_query,
    generate_sql,
)
from src.automata import sensor_machine, intervention_machine, vehicle_machine
from src.ai_report import generate_report


st.set_page_config(
    page_title="Neo-Sousse 2030",
    page_icon="🌆",
    layout="wide",
)

init_database(seed=True)


def df_query(sql: str, params=()) -> pd.DataFrame:
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        return pd.DataFrame.from_records(
            [tuple(row) for row in cursor.fetchall()],
            columns=[column[0] for column in cursor.description],
        )


@st.cache_resource
def dot_graph(machine_name: str, state: str) -> str:
    if machine_name == "capteur":
        return sensor_machine(state).dot()
    if machine_name == "intervention":
        return intervention_machine(state).dot()
    return vehicle_machine(state).dot()


st.title("Neo-Sousse 2030")
st.caption("Plateforme intelligente de gestion urbaine")

tab_accueil, tab_requete, tab_capteurs, tab_interventions, tab_vehicules, tab_rapport = st.tabs([
    "Accueil",
    "Assistant NL → SQL",
    "Capteurs",
    "Interventions",
    "Véhicules",
    "Rapports IA",
])

with tab_accueil:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capteurs", df_query("SELECT COUNT(*) AS n FROM capteurs").iloc[0]["n"])
    c2.metric("Citoyens", df_query("SELECT COUNT(*) AS n FROM citoyens").iloc[0]["n"])
    c3.metric("Véhicules", df_query("SELECT COUNT(*) AS n FROM vehicules").iloc[0]["n"])
    c4.metric("Mesures", df_query("SELECT COUNT(*) AS n FROM mesures").iloc[0]["n"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pollution moyenne par zone")
        data = df_query(
            """SELECT z.nom AS zone, ROUND(AVG(m.valeur), 2) AS moyenne
               FROM mesures m JOIN zones z ON z.zone_id=m.zone_id
               GROUP BY z.nom ORDER BY moyenne DESC"""
        )
        st.plotly_chart(px.bar(data, x="zone", y="moyenne", color="moyenne",
                               color_continuous_scale="Reds"), use_container_width=True)
    with col2:
        st.subheader("État des capteurs")
        data = df_query("SELECT statut, COUNT(*) AS nombre FROM capteurs GROUP BY statut")
        st.plotly_chart(px.pie(data, names="statut", values="nombre", hole=.45),
                        use_container_width=True)

with tab_requete:
    st.subheader("Posez une question, le LLM écrit la requête SQL")
    st.write(
        "Décrivez les données que vous recherchez en français. "
        "L'IA génère le SQL, qui est affiché puis exécuté en lecture seule."
    )
    st.caption(
        "Exemples : « affiche les 5 zones les plus polluées », "
        "« combien de capteurs sont hors service ? », "
        "« liste les citoyens avec un score supérieur à 80 »."
    )
    with st.form("natural_language_sql"):
        query = st.text_input(
            "Votre question",
            placeholder="Ex. affiche les 5 zones les plus polluées en mars",
        )
        submitted = st.form_submit_button("Générer et exécuter avec l'IA", type="primary")

    if submitted:
        try:
            with st.spinner("Le LLM transforme votre question en SQL..."):
                sql = generate_sql(query)
            st.success("Requête SQL générée par l'IA")
            st.code(sql, language="sql")
            with get_connection() as conn:
                result, truncated = execute_readonly_query(conn, sql)
            st.dataframe(result, use_container_width=True)
            if truncated:
                st.info("Affichage limité aux 500 premières lignes.")
            if len(result) and len(result.columns) >= 2:
                st.bar_chart(result.set_index(result.columns[0]))
        except (LLMConfigurationError, LLMGenerationError, UnsafeQueryError) as exc:
            st.error(str(exc))

with tab_capteurs:
    st.subheader("État des capteurs")
    df = df_query("""
        SELECT c.*, z.nom AS zone
        FROM capteurs c JOIN zones z ON z.zone_id=c.zone_id
        ORDER BY c.capteur_id
    """)
    status_filter = st.multiselect("Filtrer par état", sorted(df["statut"].unique()))
    if status_filter:
        df = df[df["statut"].isin(status_filter)]
    st.dataframe(df, use_container_width=True)

    with get_connection() as conn:
        if conn.execute("SELECT COUNT(*) FROM capteurs").fetchone()[0]:
            sensor_id = st.selectbox("Capteur à simuler", df["capteur_id"].tolist())
            sensor = conn.execute(
                "SELECT statut FROM capteurs WHERE capteur_id=?", (sensor_id,)
            ).fetchone()
            state = sensor["statut"]
            machine = sensor_machine(state)
            st.info(f"État courant : **{state}**")
            event = st.selectbox("Événement", [""] + machine.available_events())
            if st.button("Déclencher"):
                if not event:
                    st.warning("Sélectionnez un événement.")
                else:
                    try:
                        new_state, action = machine.trigger(event)
                        conn.execute(
                            "UPDATE capteurs SET statut=?, taux_erreur=CASE WHEN ?='HORS_SERVICE' THEN 15 ELSE taux_erreur END WHERE capteur_id=?",
                            (new_state, new_state, sensor_id),
                        )
                        conn.commit()
                        st.success(f"{sensor_id} → {new_state}" + (f". Action: {action}" if action else ""))
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

            st.graphviz_chart(machine.dot())

with tab_interventions:
    st.subheader("Cycle de validation des interventions")
    interventions = df_query(
        """SELECT i.*, z.nom AS zone
           FROM interventions i LEFT JOIN zones z ON z.zone_id=i.zone_id
           ORDER BY i.demande_at DESC"""
    )
    st.dataframe(interventions, use_container_width=True)

    intervention_id = st.selectbox("Intervention", interventions["intervention_id"].tolist())
    with get_connection() as conn:
        status_row = conn.execute(
            "SELECT statut FROM interventions WHERE intervention_id=?",
            (int(intervention_id),),
        ).fetchone()
        state = status_row["statut"].replace("TECH1_ASSigne", "TECH1_ASSigne")
    machine = intervention_machine(state)
    st.info(f"État courant : **{state}**")
    event = st.selectbox("Événement de validation", [""] + machine.available_events())
    if st.button("Exécuter la transition"):
        if not event:
            st.warning("Sélectionnez un événement.")
        else:
            try:
                new_state, action = machine.trigger(event)
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE interventions SET statut=? WHERE intervention_id=?",
                        (new_state, int(intervention_id)),
                    )
                    conn.commit()
                st.success(f"Intervention {intervention_id} → {new_state}. {action or ''}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.graphviz_chart(machine.dot())

with tab_vehicules:
    st.subheader("Trajets des véhicules autonomes")
    vehicles = df_query("SELECT * FROM vehicules ORDER BY vehicule_id")
    st.dataframe(vehicles, use_container_width=True)
    vehicle_id = st.selectbox("Véhicule", vehicles["vehicule_id"].tolist())
    with get_connection() as conn:
        state = conn.execute(
            "SELECT statut FROM vehicules WHERE vehicule_id=?", (vehicle_id,)
        ).fetchone()["statut"]
    machine = vehicle_machine(state)
    event = st.selectbox("Événement véhicule", [""] + machine.available_events())
    if st.button("Changer l'état"):
        if event:
            try:
                new_state, action = machine.trigger(event)
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE vehicules SET statut=? WHERE vehicule_id=?",
                        (new_state, vehicle_id),
                    )
                    conn.commit()
                st.success(f"{vehicle_id} → {new_state}. {action or ''}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.graphviz_chart(machine.dot())
    st.subheader("Trajets et économies de CO2")
    trips = df_query(
        """SELECT t.*, v.modele FROM trajets t JOIN vehicules v
           ON v.vehicule_id=t.vehicule_id ORDER BY economie_co2 DESC"""
    )
    st.plotly_chart(px.bar(trips, x="vehicule_id", y="economie_co2",
                           color="modele"), use_container_width=True)

with tab_rapport:
    st.subheader("Génération de rapport avec IA")
    date = st.date_input("Date du rapport", value=pd.Timestamp("2026-03-15"))
    if st.button("Générer le rapport", type="primary"):
        with get_connection() as conn:
            report = generate_report(conn, date.strftime("%Y-%m-%d"))
        st.markdown(f"## {report['title']}")
        st.write(report["text"])
        st.success("Actions recommandées")
        st.write(report["actions"])
