# Dépannage

## L'application ne démarre pas

Vérifier la version de Python et les dépendances :

```powershell
python --version
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

## `No module named streamlit` ou autre module absent

Exécuter :

```powershell
python -m pip install -r requirements.txt
```

La commande doit être lancée avec le même interpréteur Python que celui utilisé pour Streamlit.

## Aucun pilote ODBC disponible

Lister les pilotes reconnus :

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

Installer ou sélectionner un pilote présent dans la liste, puis adapter `driver` dans `.streamlit/secrets.toml`.

## Échec de connexion SQL

Vérifier dans cet ordre :

1. le nom du pilote ;
2. le nom du serveur et le port ;
3. le nom de la base ;
4. l'accès au réseau de l'établissement ;
5. le mode d'authentification ;
6. la valeur de `trust_server_certificate`.

Utiliser le bouton **Tester la connexion** avant de lancer les trois extractions.

## Script SQL introuvable

Le dossier `sql/` doit contenir :

```text
query_aria__strasbourg.sql
all_patient_formulaire.sql
all_patient_ethos.sql
```

Vérifier également la valeur du champ **Dossier des scripts SQL** dans l'onglet Import.

## Les fichiers ne sont pas détectés

Vérifier :

- le dossier indiqué dans l'onglet Import ;
- le nom de base du fichier ;
- l'extension `.csv`, `.xlsx` ou `.zip` ;
- les droits de lecture du dossier.

## Colonnes `pt_id` ou `date_event` manquantes

Ces deux colonnes sont obligatoires dans `formulaire_patient`. Vérifier l'en-tête du fichier et l'absence de décalage lié au séparateur CSV.

## Erreur de lecture CSV ou décalage des colonnes

Le lecteur gère automatiquement les séparateurs usuels et les guillemets doubles. En cas d'échec :

- vérifier que chaque ligne utilise le même séparateur ;
- contrôler les guillemets non fermés ;
- tester une réexportation en UTF-8 avec séparateur virgule ou point-virgule ;
- vider le cache Streamlit depuis le menu de l'application puis relancer.

## Erreur mémoire avec un grand formulaire

Privilégier le CSV au format ZIP ou CSV direct, limiter le nombre de variables sélectionnées et laisser le calcul des compteurs désactivé. Le pipeline relit les variables choisies par morceaux lors de la construction.

## Aucun patient du traitement ne correspond au formulaire

Comparer le contenu de `pt_id` dans les deux sources et vérifier :

- zéros initiaux ;
- valeurs décimales ajoutées par Excel ;
- identifiant technique différent de l'identifiant affiché ;
- cellules vides ou caractères non numériques.

L'application normalise les identifiants, mais elle ne peut pas rapprocher deux systèmes d'identification sans valeur commune.

## Le profil ne retrouve pas certaines colonnes

Consulter le diagnostic de correspondance du profil. Vérifier le libellé source, puis utiliser la recherche flexible. Les variations d'accents et d'espaces sont prises en charge, mais une variable réellement renommée doit être associée manuellement.

## L'export contient beaucoup de colonnes `NA`

Vérifier les phases activées, les fenêtres temporelles et la présence réelle de valeurs dans la cohorte. L'interface permet de retirer les colonnes entièrement vides au moment du téléchargement.
