# Neo-Sousse 2030

Plateforme Smart City avec compilation NL vers SQL, automates à états finis,
génération de rapports et tableau de bord interactif.

## Fonctionnalités

- Base urbaine avec zones, citoyens, capteurs, interventions, véhicules et séries de mesures.
- Jeu de données reproductible comprenant plus de 1000 mesures.
- Conversion des questions en SQL par LLM Groq, avec affichage de la requête générée.
- Exécution SQL en lecture seule, limitée aux tables Smart City et à 500 résultats.
- Automates déterministes pour les capteurs, interventions et véhicules.
- Rapport IA local et intégration optionnelle OpenAI via variable d'environnement.
- Dashboard Streamlit avec tableaux, graphiques et visualisation Graphviz.
- Schéma PostgreSQL de référence dans `schema.sql`.

## Installation

```powershell
cd "C:\Users\mouhamed ali\Bureau\projetgithub\samrt-city"
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Ouvrir l'adresse affichée par Streamlit, généralement `http://localhost:8501`.

## Configuration IA optionnelle

Créer une clé gratuite sur [GroqCloud](https://console.groq.com/keys), puis renseigner
`GROQ_API_KEY` et éventuellement `GROQ_MODEL` dans `.env`.
La clé est lue localement et n'est jamais affichée dans l'interface.
L'onglet « Assistant NL → SQL » utilise Groq (`qwen/qwen3.8-27b` par défaut); les rapports restent
disponibles localement sans clé IA.

## Base de données

SQLite reste la configuration locale par défaut. Le projet prend également en
charge PostgreSQL. La création idempotente des tables et le chargement du jeu
de démonstration sont automatiques au premier démarrage.

1. Démarrez PostgreSQL et créez une base vide nommée `neossousse` (par exemple
   dans pgAdmin: clic droit sur **Databases** → **Create** → **Database**).
2. Dans `.env`, configurez l'URL en remplaçant `VOTRE_MOT_DE_PASSE` par le mot
   de passe de votre utilisateur PostgreSQL:

   ```env
   DATABASE_URL=postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/neossousse
   ```

3. Installez les dépendances et redémarrez Streamlit. Le schéma `schema.sql`
   et les données de démonstration seront créés automatiquement.

Si le mot de passe contient des caractères spéciaux (`@`, `:`, `/`, `#`),
encodez-les en URL (par exemple `@` devient `%40`). Pour revenir à SQLite,
remettez `DATABASE_URL=sqlite:///data/smart_city.db`.

La connexion PostgreSQL doit viser une base dédiée vide. L'application crée
les tables, mais ne copie pas automatiquement les données d'une base SQLite
existante.

## Tests

```powershell
pytest -q
```

## Requêtes prises en charge

- `Affiche les 5 zones les plus polluées`
- `Combien de capteurs sont hors service ?`
- `Quels citoyens ont un score écologique > 80 ?`
- `Donne-moi le trajet le plus économique en CO2`
- `Quelles interventions sont en cours ?`
- `Affiche les 20 dernières mesures`
