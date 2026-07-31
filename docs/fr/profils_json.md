# Profils JSON

## 1. Objet

Un profil JSON enregistre une configuration d'extraction afin de la réutiliser avec une nouvelle extraction des mêmes sources. Il mémorise les choix de variables sans modifier les données d'origine.

## 2. Structure générale

```json
{
  "version": "ARIA_ODM_profile_v1",
  "created_at": "2026-07-30T09:00:00",
  "settings": {},
  "columns": []
}
```

- `version` identifie le format du profil ;
- `created_at` indique la date de création ;
- `settings` contient les paramètres généraux ;
- `columns` décrit les variables de formulaire.

## 3. Paramètres généraux

Les paramètres peuvent notamment contenir :

- zone ou nom d'export ;
- mode et valeurs CIM10 ;
- critère de dose non nulle ;
- référence des délais ;
- colonnes traitement ;
- listes de semaines ;
- suppression des doublons ;
- tables de décodage de codes binaires.

## 4. Configuration des variables

Chaque entrée de `columns` peut contenir :

| Champ | Fonction |
|---|---|
| `Inclure` | active la variable |
| `Colonne formulaire` | nom de la colonne source |
| `Nom export` | nom utilisé dans le fichier final |
| `Cumul` | active les colonnes cumulées |
| `Avant RT` | active les fenêtres antérieures au traitement |
| `Aigu` | active les fenêtres pendant le traitement |
| `Tardif` | active les fenêtres après le traitement |
| champs de décodage | décrivent la conversion éventuelle des codes binaires |

## 5. Correspondance avec un nouveau formulaire

Lors du chargement, l'application recherche les colonnes du profil dans le formulaire courant. La correspondance accepte les différences d'accents, d'espaces, de ponctuation, de retours à la ligne et certains défauts d'encodage. Les colonnes non retrouvées sont recensées dans le diagnostic de profil.

Le profil reste éditable : l'utilisateur peut ajouter, retirer ou renommer des variables avant de construire l'export.

## 6. Décodage des choix binaires

Certaines variables sont enregistrées sous forme de chaînes binaires telles que `00100` ou `01001`. Une table de décodage peut associer chaque position à un libellé ou à un grade. Lorsqu'une observation contient plusieurs positions actives, l'application combine les libellés ou conserve le grade maximal selon le mode défini.

## 7. Création d'un profil

Après la construction d'un export, le bouton **Sauvegarder profil JSON** génère un profil à partir de la configuration courante. Ce fichier peut ensuite être rechargé dans l'onglet Import ou modifié depuis l'onglet Profil.
