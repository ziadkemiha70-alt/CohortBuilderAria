# Tests et validation

## 1. Objectif

La validation vise à confirmer qu'une modification conserve le comportement attendu du pipeline : chargement, cohorte, temporalités, agrégation, décodage et génération des sorties.

## 2. Jeu de test

Utiliser un jeu de données fictif comprenant au minimum :

- plusieurs patients et codes CIM10 ;
- des traitements standards et ETHOS ;
- des dates avant, pendant et après la radiothérapie ;
- des valeurs numériques, textuelles et binaires ;
- des doublons exacts ;
- une colonne absente d'un profil ;
- une dose nulle et une dose multi-valeurs ;
- plusieurs enregistrements TNM pour un même patient.

## 3. Scénarios fonctionnels

| Scénario | Résultat attendu |
|---|---|
| lancement sans erreur | les six onglets sont accessibles |
| mode fichiers existants | les trois sources sont détectées selon leur présence |
| test de connexion SQL | un message de réussite est affiché |
| filtre CIM10 simple | seuls les patients correspondants sont retenus |
| CIM10 multiples dans une cellule | un code demandé suffit à retenir la ligne |
| dose multi-valeurs | une valeur non nulle conserve le traitement |
| intégration ETHOS | les patients de la cohorte sont enrichis |
| profil JSON | les variables retrouvées sont présélectionnées |
| code binaire | les zéros initiaux et le décodage sont conservés |
| doublon exact | il est recensé et supprimé si l'option est active |
| construction | Excel, CSV, rapport de preuve et profil sont générés |

## 4. Validation des temporalités

Pour chaque phase, préparer des dates situées précisément aux limites des fenêtres. Vérifier :

- l'affectation à la bonne semaine ou au bon intervalle mensuel ;
- le calcul du délai par rapport à la référence choisie ;
- la règle de première observation pour les fenêtres non cumulatives ;
- la conservation chronologique pour les cumuls.

## 5. Validation des fichiers générés

Contrôler :

- une ligne par patient dans l'export final ;
- la présence des colonnes traitement sélectionnées ;
- l'absence des colonnes techniques `_aria_*` ;
- la représentation des valeurs manquantes par `NA` ;
- la cohérence entre le schéma annoncé et les colonnes produites ;
- l'ouverture des fichiers Excel sans message de réparation.

## 6. Critères d'acceptation

Une version est considérée comme validée lorsque tous les scénarios applicables réussissent, qu'aucune erreur bloquante n'apparaît dans l'interface et que les écarts signalés par le rapport de preuve sont compris et documentés.
