# Données d'entrée et sorties

## 1. Formats acceptés

Selon la source et le mode de lecture, l'application accepte les formats CSV, XLSX et ZIP contenant un CSV. Les noms de base recherchés sont :

```text
traitement_patient
formulaire_patient
ethos_patient
```

L'application recherche en priorité les extensions `.csv`, `.xlsx` puis `.zip`.

## 2. `traitement_patient`

Cette source constitue la base de la cohorte. Elle peut contenir :

- identifiants patient techniques et fonctionnels ;
- codes diagnostiques CIM10 ;
- dates de première et dernière fraction ;
- dose totale et nombre de fractions réalisées ;
- plan, technique, machine et informations de traitement ;
- données tumorales, notamment les couples `TNM_n` / `Date_staged_n`.

Les noms peuvent varier entre versions. L'application reconnaît plusieurs alias pour les champs structurants.

## 3. `formulaire_patient`

Cette source contient les observations issues des formulaires et questionnaires. Deux colonnes sont indispensables :

| Colonne | Rôle |
|---|---|
| `pt_id` | identifiant utilisé pour le rapprochement |
| `date_event` | date de l'observation |

Les autres colonnes représentent les variables sélectionnables dans l'interface. Elles sont chargées à la demande afin d'éviter de conserver en mémoire l'intégralité d'un formulaire très large.

## 4. `ethos_patient`

Cette source est optionnelle. L'application conserve les lignes exploitables selon la présence des dates et d'une dose réalisée non nulle, puis les fusionne avec les traitements standards.

## 5. Mapping

Le mapping peut être fourni au format CSV ou Excel. Il associe des codes CIM10 à des descriptions, localisations ou groupes de variables et sert d'aide à la sélection. Il ne conditionne pas l'exécution du pipeline.

## 6. Profil JSON

Le profil contient les variables retenues, leurs noms d'export, les phases temporelles et les paramètres d'agrégation. Sa structure est décrite dans [profils_json.md](profils_json.md).

## 7. Sorties

| Sortie | Contenu |
|---|---|
| Excel final | une ligne par patient et les colonnes sélectionnées |
| CSV final | même contenu au format texte, séparateur point-virgule |
| Rapport de preuve | contrôles, paramètres, schéma et échantillons de traçabilité |
| Profil JSON | configuration réutilisable de l'extraction |

Le nom des fichiers est dérivé de la localisation, du profil ou du CIM10 sélectionné.

## 8. Représentation des valeurs manquantes

Les valeurs absentes sont représentées par `NA` dans les exports. Les colonnes entièrement vides sont signalées avant le téléchargement et peuvent être retirées de la sortie finale.
