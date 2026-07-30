# Guide utilisateur

## 1. Choisir le mode d'import

Dans l'onglet **Import**, sélectionner l'une des deux options :

- **Faire l'extraction SQL ici** : l'application exécute les requêtes du dossier `sql/` et génère les fichiers demandés ;
- **Extraction déjà faite** : l'application charge les fichiers présents dans le dossier indiqué.

Les deux modes alimentent le même pipeline de construction.

## 2. Charger les sources

Les sources principales sont :

- `traitement_patient` : traitements, dates, doses, fractions, diagnostics et informations techniques ;
- `formulaire_patient` : observations cliniques datées ;
- `ethos_patient` : source complémentaire optionnelle pour les traitements ETHOS.

Le mapping et le profil JSON sont optionnels. Le mapping aide à interpréter les localisations et le profil rétablit une configuration d'extraction enregistrée.

## 3. Définir la cohorte

Dans l'onglet **Construction** :

1. saisir un ou plusieurs codes CIM10 ;
2. choisir le mode de filtrage CIM10 ;
3. activer, si nécessaire, le critère de dose non nulle ;
4. examiner le nombre de lignes et de patients retenus.

Le traitement standard définit la cohorte principale. Lorsqu'une source ETHOS est chargée, elle enrichit les patients retenus sans modifier la logique de sélection principale.

## 4. Choisir les colonnes traitement

L'application propose les colonnes disponibles dans les sources de traitement. Les colonnes techniques créées pour résoudre les différences entre versions d'extraction restent utilisées en interne et sont exclues de l'export final.

Les couples `TNM_n` et `Date_staged_n` sont détectés et conservés lorsqu'ils sont présents.

## 5. Sélectionner les variables formulaire

La table de sélection permet de :

- inclure ou exclure une variable ;
- modifier son nom dans l'export ;
- consulter sa catégorie et son score de pertinence ;
- rechercher une colonne avec une recherche tolérante aux accents, espaces et variations d'encodage.

Le calcul des compteurs de valeurs et de patients est optionnel afin de conserver une interface réactive avec les formulaires volumineux.

## 6. Régler les temporalités

Pour chaque variable incluse, activer les phases souhaitées :

- **Cumul** ;
- **Avant RT** ;
- **Pendant RT / Aigu** ;
- **Après RT / Tardif**.

Les paramètres détaillés sont décrits dans [temporalites.md](temporalites.md).

## 7. Construire l'export

Cliquer sur **Construire / recalculer**. L'application :

1. relit uniquement les variables sélectionnées dans le formulaire ;
2. associe les observations à la cohorte ;
3. calcule les délais par rapport à `startD` et `endD` ;
4. applique les règles temporelles et les éventuels décodages du profil ;
5. assemble les données traitement et formulaire ;
6. produit les contrôles et le rapport de preuve.

## 8. Télécharger les résultats

Quatre sorties peuvent être téléchargées :

- export final Excel ;
- export final CSV ;
- rapport de preuve Excel ;
- profil JSON correspondant à la sélection courante.

L'interface permet également de retirer les colonnes entièrement vides avant le téléchargement final.
