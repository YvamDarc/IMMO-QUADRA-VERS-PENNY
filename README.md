# PDF immobilisations → Pennylane

Application Streamlit pour les PDF texte « Etat des dotations B.I.C. - B.A. » ayant la même présentation que le modèle fourni. Import des fiches dans le module Immobilisations, pas des écritures comptables.

## Mise en ligne sur Streamlit Community Cloud

1. Créer un dépôt GitHub pour cette application.
2. Déposer `app.py`, `converter.py` et `requirements.txt` à la racine, sans les renommer.
3. Dans Streamlit Community Cloud, créer une application à partir du dépôt.
4. Choisir `app.py` comme fichier principal et Python 3.12 dans les paramètres avancés.
5. Déployer puis déposer le PDF dans l'application.

Le PDF du client et ses CSV ne doivent pas être ajoutés au dépôt de code. Sur un hébergement distant, le PDF est transmis au serveur Streamlit pour traitement ; aucun service de conversion ou d'IA tiers n'est appelé. L'application ne sauvegarde pas les PDF sur disque.

En local, facultatif : `python -m pip install -r requirements.txt` puis `python -m streamlit run app.py`.

## Utilisation

- Déposer un PDF, vérifier les totaux par compte et le détail extrait.
- Choisir la reprise : début de l'exercice = colonne Antérieur ; lendemain de clôture = colonne Total.
- Modifier comptes, libellés, dates, durées et montants dans le tableau. Décocher Inclure pour écarter un bien.
- Choisir l'unité de durée demandée par le mapping Pennylane (mois ou années).
- Télécharger le CSV UTF-8 avec BOM, séparateur point-virgule par défaut et décimales avec virgule.
- Importer dans Révision > Immobilisations > Import de fichiers > Excel / CSV, puis mapper les colonnes. Vérifier en particulier valeur amortie, durée et exercice de reprise. Les comptes doivent exister dans le dossier.

La référence peut rester non mappée si aucun champ correspondant n'est proposé. Pour une date de cession, utiliser le champ de sortie proposé par l'importateur ; à défaut, gérer les sorties dans les fiches. Aucun montant ni motif de cession n'est inventé.

## Hypothèses à vérifier

- La date d'acquisition du PDF est proposée aussi comme début d'amortissement : le PDF ne distingue pas ces deux dates.
- Les durées linéaires sont estimées par `arrondi(1200 / taux)` en mois. Un taux 14,29 % donne 84 mois et 6,67 % donne 180 mois. Vérifier les durées d'origine : un taux arrondi ne les prouve pas.
- Une durée dégressive n'est pas déduite automatiquement : elle doit être renseignée.
- N devient Non amortissable. Les valeurs nulles dans les colonnes monétaires du tableau sont interprétées comme zéro.
- Une VNC nulle ne provoque jamais une sortie. La VNC du PDF n'est pas exportée comme valeur résiduelle contractuelle.
- Les comptes ne sont ni tronqués ni renumérotés automatiquement.
- Les dates à six chiffres sont interprétées comme JJMM AA, dans le dernier siècle compatible avec l'année de clôture du PDF.
- Les récapitulatifs ne sont pas importés comme des biens. Les lignes fournisseurs sont ignorées et les suites de libellés sont rattachées.

## Périmètre et limites

Validé sur le PDF fourni : 33 fiches, brut 205 042,64 €, antérieur 141 039,47 €, dotation 24 078,01 €, cumul 165 117,48 €, VNC 39 925,16 €. Les 20 contrôles de sommes par compte sont exacts.

Le parseur reconnaît des références à cinq chiffres suivies d'un composant à trois chiffres et les colonnes de cette édition. Un scan exige un OCR préalable ; une autre présentation nécessite une adaptation. Les anomalies sont affichées, un détail reste téléchargeable et les anomalies d'extraction doivent être reconnues avant export.

Le CSV utilise le mapping de colonnes documenté par Pennylane, pas une trame universelle à colonnes imposées. La documentation publique ne fournit pas ici la liste exhaustive des champs obligatoires ni leurs unités ; vérifier l'aperçu d'import et le cadrage des amortissements après import. Aucun test d'import dans un dossier Pennylane connecté n'a été effectué.

Documentation consultée le 06/10/2026 :
https://help.pennylane.com/fr/articles/18684-importer-un-etat-des-immobilisations
