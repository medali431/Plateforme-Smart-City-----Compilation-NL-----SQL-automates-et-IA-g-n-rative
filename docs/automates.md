# Modélisation des automates

## Capteur

```mermaid
stateDiagram-v2
    [*] --> INACTIF
    INACTIF --> ACTIF: installation
    ACTIF --> SIGNALE: détection d'anomalie
    ACTIF --> HORS_SERVICE: panne
    SIGNALE --> EN_MAINTENANCE: assignation maintenance
    SIGNALE --> HORS_SERVICE: panne
    SIGNALE --> ACTIF: réparation
    EN_MAINTENANCE --> ACTIF: réparation
```

| État source | Événement | État cible | Action |
|---|---|---|---|
| INACTIF | installation | ACTIF | Activer la surveillance |
| ACTIF | détection d'anomalie | SIGNALE | Créer une demande |
| ACTIF | panne | HORS_SERVICE | Envoyer une alerte |
| SIGNALE | panne | HORS_SERVICE | Envoyer une alerte |
| SIGNALE | réparation | ACTIF | Fermer l'alerte |
| EN_MAINTENANCE | réparation | ACTIF | Remettre en service |

## Validation d'intervention

```mermaid
stateDiagram-v2
    [*] --> DEMANDE
    DEMANDE --> TECH1_ASSigne: assignation tech1
    TECH1_ASSigne --> TECH2_VALIDE: validation tech2
    TECH2_VALIDE --> IA_VALIDE: validation IA
    IA_VALIDE --> TERMINE: clôture
```

## Véhicule autonome

```mermaid
stateDiagram-v2
    [*] --> STATIONNE
    STATIONNE --> EN_ROUTE: démarrage
    EN_ROUTE --> EN_PANNE: panne
    EN_ROUTE --> ARRIVE: arrivée
    EN_PANNE --> STATIONNE: réparation
```

