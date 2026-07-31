# Temporalités

## 1. Dates de référence

Pour chaque patient, l'application calcule :

- `startD` : première date de radiothérapie retenue ;
- `endD` : dernière date de radiothérapie retenue.

Chaque observation de formulaire reçoit ensuite un délai en jours par rapport à ces dates.

## 2. Phases disponibles

### Cumul

Regroupe toutes les observations disponibles pour une variable. Les valeurs, dates et délais sont conservés dans des colonnes distinctes.

### Avant RT

Regroupe les observations antérieures à `startD`. L'application peut produire un cumul antérieur et des fenêtres hebdomadaires définies par l'utilisateur.

### Pendant RT / Aigu

Regroupe les observations à partir de `startD` pendant la période aiguë. Les fenêtres sont exprimées en semaines de traitement.

### Après RT / Tardif

Regroupe les observations postérieures à `endD`. Des fenêtres hebdomadaires et des intervalles mensuels sont générés.

## 3. Paramètres par défaut

Les valeurs par défaut du code sont :

- semaines avant RT : 71, 48, 41, 40, 37, 29, 13, 10, 8, 7, 6, 5, 4, 3, 2 et 1 ;
- semaines pendant RT : 1 à 7 ;
- semaines après RT : 1 et 8 ;
- intervalles mensuels : mois 1, 2-4, 5-7, puis intervalles successifs jusqu'à 62 mois et plus.

Ces listes peuvent être adaptées dans l'interface en mode expert.

## 4. Nommage des colonnes

Pour une variable nommée `Douleur`, le schéma peut produire :

```text
Douleur_Cumul
Douleur_Cumul_Date
Douleur_Cumul_Delai
Douleur_AvantRT_Semaine_001
Douleur_PendantRT_Semaines_001
Douleur_ApresRT_Semaine_001
Douleur_Mois 02 - 04
```

Chaque colonne de valeur peut être accompagnée d'une colonne de date et d'une colonne de délai.

## 5. Agrégation

Pour plusieurs valeurs le même jour :

- une valeur répétée est conservée une seule fois ;
- des valeurs numériques sont résolues par le maximum ;
- des codes binaires sont fusionnés par un OU logique ;
- des valeurs textuelles différentes sont résolues par la dernière valeur non vide.

Pour une fenêtre non cumulative, la première date de la fenêtre est retenue. Pour une colonne cumulative, toutes les observations sont conservées dans l'ordre chronologique.

## 6. Doublons exacts

Un doublon exact correspond au même patient, à la même variable, à la même date et à la même valeur. L'application peut le supprimer de l'agrégation tout en le recensant dans le rapport de preuve.
