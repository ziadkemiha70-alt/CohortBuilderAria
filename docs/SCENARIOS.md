# Scénarios utilisateur — ARIA ODM Builder

| Narration utilisateur | Action correspondante dans l'application |
|---|---|
| L'utilisateur arrive sur l'application et veut comprendre le rôle de l'outil. | Il lit l'onglet **Accueil**, qui présente le contexte ARIA/MOSAIQ, le workflow et les fichiers attendus. |
| L'utilisateur veut charger les données patients. | Il va dans **Import** et charge `traitement_patient` puis `formulaire_patient`. |
| L'utilisateur veut ajouter une aide CIM10/localisation. | Il charge `mapping.csv` depuis `conf/` ou via l'upload optionnel. |
| L'utilisateur veut réutiliser une configuration validée. | Il importe un profil JSON depuis `conf/profiles/`. |
| L'utilisateur veut construire une cohorte. | Il va dans **Construction**, choisit le mode CIM10, saisit les codes, règle les options puis clique sur **Construire / recalculer**. |
| L'utilisateur veut éviter les recalculs inutiles. | Il modifie les paramètres, puis lance explicitement le calcul avec le bouton de construction. |
| L'utilisateur veut vérifier la cohérence des données. | Il consulte **Contrôle qualité** pour vérifier les jointures, dates, doublons et valeurs longues conservées. |
| L'utilisateur veut comprendre l'origine des colonnes exportées. | Il consulte **Sources** pour visualiser le schéma et les colonnes formulaire sources. |
| L'utilisateur veut sauvegarder son travail. | Il va dans **Profil** et exporte un JSON réutilisable. |
| L'utilisateur revient avec de nouveaux fichiers. | Il importe les nouveaux fichiers, recharge le profil JSON et relance **Construire / recalculer**. |
