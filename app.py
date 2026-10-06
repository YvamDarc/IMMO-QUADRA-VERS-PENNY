from hashlib import sha256
import pandas as pd
import streamlit as st
from converter import extract_pdf, prepare_import, csv_bytes

st.set_page_config(page_title='PDF immos → Pennylane', page_icon='📄', layout='wide')
st.title('PDF immobilisations → Pennylane')
st.write('Transformez un état des dotations B.I.C. – B.A. en CSV pour le module Immobilisations.')
st.caption('PDF texte de même présentation que le modèle fourni • Lecture sans OCR • Aucun envoi à un service de conversion externe')
f = st.file_uploader('Déposez votre état des dotations PDF', type=['pdf'])
if f is None:
    st.info('Déposez un PDF pour afficher les immobilisations, contrôler les totaux et télécharger le CSV.')
    st.stop()
data = f.getvalue()
id_file = sha256(data).hexdigest()[:16]
try:
    raw, checks, issues, start, end = extract_pdf(data)
except Exception as exc:
    st.error(str(exc))
    st.stop()
st.caption(f'Période du PDF : {start:%d/%m/%Y} au {end:%d/%m/%Y}')
cols = st.columns(4)
for c, name, value in zip(cols, ['Immobilisations', 'Valeur brute', 'Dotations exercice', 'Cumul fin exercice'],
                          [str(len(raw))] + [f'{raw[k].sum():,.2f} €'.replace(',', ' ').replace('.', ',') for k in ['Montant HT','Exercice','Total']]):
    c.metric(name,value)
with st.expander('Contrôle de l’extraction et totaux par compte', expanded=bool(issues)):
    st.dataframe(checks, hide_index=True, width='stretch')
    st.dataframe(raw, hide_index=True, width='stretch')
    st.download_button('Télécharger le détail extrait', csv_bytes(raw), 'detail_extraction.csv', 'text/csv')
    for issue in issues:
        st.warning(issue)
bad = bool(issues) or (not checks.empty and (checks['Écart'].abs() > .01).any())
if bad:
    st.warning('Extraction à vérifier : consultez le détail ci-dessus. Le téléchargement de contrôle reste disponible.')
choice = st.radio('À partir de quand Pennylane doit-il calculer les dotations ?',
                  ['Après la clôture du PDF — reprendre le cumul Total', 'Dès le début de l’exercice du PDF — reprendre le cumul Antérieur'])
after = choice.startswith('Après')
st.info('Les durées linéaires sont estimées à partir des taux arrondis du PDF (14,29 % → 84 mois ; 6,67 % → 180 mois). '
        'La date de début d’amortissement est proposée égale à la date d’acquisition. Vérifiez ces deux paramètres. '
        'Pour un amortissement dégressif, renseignez vous-même la durée.')
st.caption('Les biens totalement amortis sont conservés. Une date de cession est reprise uniquement si elle figure dans le PDF. '
           'La VNC du PDF n’est pas une valeur résiduelle contractuelle et n’est pas exportée comme telle.')
base = prepare_import(raw, start, end, after)
if not after:
    st.caption('Les acquisitions et cessions de l’exercice figurent aussi dans l’état : adaptez la sélection si elles sont déjà gérées dans Pennylane.')
editor_key = f'editor_{id_file}_{after}'
st.subheader('Vérifier et corriger avant export')
edited = st.data_editor(base, key=editor_key, hide_index=True, width='stretch',
    column_config={'Inclure':st.column_config.CheckboxColumn(default=True),
                   'Durée (mois)':st.column_config.NumberColumn(min_value=0, step=1, format='%d'),
                   'Type d’amortissement':st.column_config.SelectboxColumn(options=['Linéaire','Dégressif','Non amortissable']),
                   'Valeur brute':st.column_config.NumberColumn(format='%.2f'),
                   'Valeur amortie':st.column_config.NumberColumn(format='%.2f')})
selected = edited[edited['Inclure']].drop(columns='Inclure').copy()
errors = []
for _, r in selected.iterrows():
    ref = r['Référence']
    if not str(r['Compte d’immobilisation']).strip().isalnum():
        errors.append(f'{ref} : compte vide ou non alphanumérique.')
    if not str(r['Libellé']).strip():
        errors.append(f'{ref} : libellé vide.')
    for col in ['Date d’acquisition','Date de début d’amortissement','Exercice de reprise','Date de cession']:
        v = r[col]
        if col == 'Date de cession' and (pd.isna(v) or not str(v).strip()):
            continue
        try:
            from datetime import datetime
            datetime.strptime(str(v), '%d/%m/%Y')
        except (ValueError, TypeError):
            errors.append(f'{ref} : {col} doit être au format JJ/MM/AAAA.')
    if pd.isna(r['Valeur brute']) or pd.isna(r['Valeur amortie']) or not (0 <= r['Valeur amortie'] <= r['Valeur brute']):
        errors.append(f'{ref} : vérifier valeur brute et valeur amortie.')
    if r['Type d’amortissement'] != 'Non amortissable' and (pd.isna(r['Durée (mois)']) or r['Durée (mois)'] <= 0):
        errors.append(f'{ref} : durée d’amortissement à compléter.')
for err in errors:
    st.error(err)
unit = st.selectbox('Unité de durée attendue dans votre mapping Pennylane', ['Mois', 'Années'])
if unit == 'Années':
    selected['Durée (années)'] = selected.pop('Durée (mois)') / 12
sep = st.selectbox('Séparateur CSV', ['Point-virgule ;', 'Virgule ,'])
ack = st.checkbox('J’ai vérifié les anomalies d’extraction et corrigé les données nécessaires.') if bad else True
st.download_button('Télécharger le CSV Pennylane', csv_bytes(selected, ';' if sep.startswith('Point') else ','),
                   f'{f.name.rsplit(".",1)[0]}_pennylane.csv', 'text/csv',
                   disabled=bool(errors) or selected.empty or not ack, type='primary')
with st.expander('Comment importer dans Pennylane ?'):
    st.markdown('''1. Ouvrir **Révision → Immobilisations → Import de fichiers → Excel / CSV**.
2. Déposer le CSV et faire correspondre les colonnes : compte, libellé, acquisition, début d’amortissement, valeur brute, type, durée, valeur amortie et exercice de reprise.
3. Vérifier l’unité de durée demandée ; le sélecteur ci-dessus permet d’exporter en mois ou en années.
4. Laisser « Référence » non mappée si aucun champ ne correspond. Mapper la date de cession uniquement si nécessaire et proposée ; traiter sinon les sorties dans les fiches.
5. Vérifier les comptes existants et l’aperçu avant validation. Contrôler ensuite les cumuls et les écarts de reprise.

[Documentation Pennylane](https://help.pennylane.com/fr/articles/18684-importer-un-etat-des-immobilisations)

CSV destiné au mapping d’import des immobilisations ; aucun import réel n’a été effectué par cette application.''')
