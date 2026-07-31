# Installation et lancement

## 1. Prérequis

Le poste doit disposer de :

- Windows 10 ou 11 ;
- Python compatible avec les dépendances du projet ;
- un accès au dossier de l'application ;
- un pilote Microsoft ODBC for SQL Server lorsque l'extraction SQL est utilisée ;
- un accès réseau au serveur ARIA pour le mode d'extraction directe.

## 2. Lancement rapide

Depuis PowerShell :

```powershell
cd "C:\chemin\vers\CohortBuilderAria"
python -m pip install -r requirements.txt
python -m streamlit run app2.py
```

La deuxième commande installe notamment Streamlit, pandas, NumPy, pyodbc, openpyxl, xlsxwriter et skrub.

## 3. Configuration SQL

Créer le fichier suivant dans le projet :

```text
.streamlit/secrets.toml
```

Exemple avec authentification Windows :

```toml
[database]
driver = "ODBC Driver 18 for SQL Server"
server = "NOM_SERVEUR,1433"
database = "NOM_BASE"
username = ""
password = ""
trusted_connection = true
trust_server_certificate = true
```

Le pilote peut être remplacé par `ODBC Driver 17 for SQL Server` selon la configuration du poste. Le fichier contient uniquement la configuration locale ; il n'est pas fourni avec l'application.

## 4. Vérification de l'environnement

Lister les pilotes ODBC reconnus :

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

Vérifier Streamlit :

```powershell
python -m streamlit --version
```

## 5. Premier démarrage

Au lancement, vérifier les points suivants :

1. l'en-tête de l'application s'affiche ;
2. les onglets Accueil, Import, Construction, Contrôle qualité, Sources et Profil sont accessibles ;
3. l'onglet Import propose le mode SQL et le mode fichiers existants ;
4. le bouton de test de connexion SQL renvoie un message de réussite lorsque ce mode est utilisé.

## 6. Utilisation sans connexion SQL

L'application peut fonctionner à partir de fichiers déjà extraits. Placer les fichiers dans `inputs/` ou indiquer un autre dossier dans l'onglet Import. Les fichiers attendus sont décrits dans [donnees_entree.md](donnees_entree.md).
