# Modèle conceptuel

## Relations

- Une zone contient plusieurs citoyens (1:N).
- Une zone accueille plusieurs capteurs (1:N).
- Une zone peut recevoir plusieurs mesures (1:N).
- Un capteur produit plusieurs mesures (1:N).
- Une capteur peut être associé à plusieurs interventions (1:N).
- Une intervention peut être assignée à deux techniciens: relation N:M via `intervention_assignments`.
- Un véhicule réalise plusieurs trajets (1:N).

## Contraintes

- Identifiants primaires sur toutes les entités.
- Clés étrangères avec intégrité référentielle.
- Domaine de score écologique entre 0 et 100.
- Domaines contrôlés pour les états des capteurs, véhicules et interventions.
- Horodatages obligatoires pour les mesures et demandes d'intervention.
- Index sur `(zone_id, mesure_at)` et `mesure_at` pour les séries temporelles.
