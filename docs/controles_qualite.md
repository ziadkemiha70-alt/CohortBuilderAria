# Contrôles qualité et rapport de preuve

## 1. Finalité

Les contrôles décrivent la cohérence technique et structurelle du pipeline : rapprochement des sources, disponibilité des dates, doublons, multiplicité de certaines informations de traitement et structure de l'export.

## 2. Contrôles principaux

Le tableau de qualité présente notamment :

- patients traitement retrouvés dans le formulaire ;
- patients de la cohorte retrouvés dans le formulaire ;
- disponibilité de `startD` et `endD` ;
- nombre de variables sélectionnées ;
- nombre d'observations de formulaire conservées ;
- doublons exacts ;
- dates de formulaire non interprétables ;
- distribution des patients selon la source de traitement ;
- multiplicité des doses, dates, fractions ou machines.

Les statuts utilisés sont `OK`, `Info` et `A vérifier`.

## 3. Cohérence du traitement

Pour chaque patient, le contrôle peut signaler plusieurs valeurs distinctes pour :

- la date de première fraction ;
- la date de dernière fraction ;
- la dose réalisée ;
- le nombre de fractions ;
- la machine.

La technique n'est pas incluse dans cette règle, car plusieurs techniques peuvent appartenir au même traitement.

## 4. Rapport de preuve

Le classeur de preuve peut contenir les feuilles suivantes :

| Feuille | Contenu |
|---|---|
| `Pipeline` | étapes et paramètres de construction |
| `Resume` | métriques principales de l'export |
| `Qualite` | résultats des contrôles |
| `Distribution_CIM10` | lignes et patients par code normalisé |
| `Selection_colonnes` | variables retenues et couverture observée |
| `Schema_colonnes` | colonnes ODM générées |
| `Colonnes_100pct_NA` | colonnes sans valeur dans la cohorte |
| `Aide_mapping` | correspondances issues du mapping |
| `Skrub_nettoyage` | opérations de nettoyage contrôlé |
| `Ethos_integration` | synthèse de l'intégration ETHOS |
| `Traitement_incoherences` | détails des valeurs multiples |
| `Doublons_exact_sample` | échantillon de doublons |
| `Formulaire_long_sample` | échantillon des observations préparées |
| `Profiling` | durées des étapes lorsque l'option est activée |

## 5. Lecture recommandée

Avant d'utiliser un export :

1. vérifier le nombre de patients ;
2. examiner les taux de rapprochement entre traitement et formulaire ;
3. contrôler la disponibilité des dates de référence ;
4. consulter les éventuelles valeurs multiples de traitement ;
5. vérifier les colonnes entièrement vides ;
6. comparer un échantillon avec les sources attendues.
