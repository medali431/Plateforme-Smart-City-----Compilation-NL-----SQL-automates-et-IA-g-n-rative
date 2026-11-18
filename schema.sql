-- Schéma PostgreSQL de référence
-- Implémentation active: SQLite dans data/smart_city.db

CREATE TABLE IF NOT EXISTS zones (
    zone_id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    secteur VARCHAR(50) NOT NULL,
    superficie_km2 NUMERIC(8,2) CHECK (superficie_km2 > 0)
);

CREATE TABLE IF NOT EXISTS citoyens (
    citoyen_id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    score_ecolo SMALLINT CHECK (score_ecolo BETWEEN 0 AND 100),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS techniciens (
    technicien_id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    specialite VARCHAR(100) NOT NULL,
    disponible BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS capteurs (
    capteur_id VARCHAR(20) PRIMARY KEY,
    type VARCHAR(100) NOT NULL,
    statut VARCHAR(30) NOT NULL CHECK (statut IN ('INACTIF','ACTIF','SIGNALE','EN_MAINTENANCE','HORS_SERVICE')),
    taux_erreur NUMERIC(5,2) CHECK (taux_erreur >= 0),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    installe_at TIMESTAMPTZ,
    hors_service_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS interventions (
    intervention_id SERIAL PRIMARY KEY,
    demande_at TIMESTAMPTZ NOT NULL,
    statut VARCHAR(30) NOT NULL CHECK (statut IN ('DEMANDE','TECH1_ASSigne','TECH2_VALIDE','IA_VALIDE','TERMINE')),
    description TEXT NOT NULL,
    priorite VARCHAR(20) CHECK (priorite IN ('basse','moyenne','haute','critique')),
    capteur_id VARCHAR(20) REFERENCES capteurs(capteur_id),
    zone_id INTEGER REFERENCES zones(zone_id)
);

CREATE TABLE IF NOT EXISTS intervention_assignments (
    intervention_id INTEGER NOT NULL REFERENCES interventions(intervention_id),
    technicien_id INTEGER NOT NULL REFERENCES techniciens(technicien_id),
    role VARCHAR(50) NOT NULL,
    PRIMARY KEY (intervention_id, technicien_id)
);

CREATE TABLE IF NOT EXISTS vehicules (
    vehicule_id VARCHAR(20) PRIMARY KEY,
    modele VARCHAR(100) NOT NULL,
    statut VARCHAR(30) NOT NULL CHECK (statut IN ('STATIONNE','EN_ROUTE','EN_PANNE','ARRIVE'))
);

CREATE TABLE IF NOT EXISTS trajets (
    trajet_id SERIAL PRIMARY KEY,
    vehicule_id VARCHAR(20) NOT NULL REFERENCES vehicules(vehicule_id),
    origine VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    debut_at TIMESTAMPTZ NOT NULL,
    fin_at TIMESTAMPTZ,
    distance_km NUMERIC(8,2),
    economie_co2 NUMERIC(8,2)
);

CREATE TABLE IF NOT EXISTS mesures (
    mesure_id BIGSERIAL PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    capteur_id VARCHAR(20) REFERENCES capteurs(capteur_id),
    type_mesure VARCHAR(50) NOT NULL,
    valeur NUMERIC(12,3) NOT NULL,
    unite VARCHAR(20) NOT NULL,
    mesure_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mesures_zone_time ON mesures(zone_id, mesure_at);
CREATE INDEX IF NOT EXISTS idx_mesures_time ON mesures(mesure_at);
