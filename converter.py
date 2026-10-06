"""Lecture d'états BIC/BA textuels, sans OCR ni service externe."""
from io import BytesIO
from datetime import datetime, timedelta
from decimal import Decimal
import re
import pdfplumber
import pandas as pd

MONEY = ['Montant HT', 'Antérieur', 'Exercice', 'Total', 'VNC']

def amount(value):
    value = str(value).replace('\u00a0', '').replace(' ', '').replace(',', '.')
    return float(Decimal(value)) if value else 0.0

def date6(value, end_year):
    value = value.strip()
    if not value:
        return ''
    if re.fullmatch(r'\d{6}', value):
        year = end_year // 100 * 100 + int(value[-2:])
        if year > end_year:
            year -= 100
        return datetime.strptime(value[:4] + str(year), '%d%m%Y').strftime('%d/%m/%Y')
    return datetime.strptime(value, '%d/%m/%Y').strftime('%d/%m/%Y')

def extract_pdf(data):
    rows, totals, issues = [], [], []
    start = end = None
    with pdfplumber.open(BytesIO(data)) as pdf:
        for page in pdf.pages:
            lines = page.extract_text_lines()
            text = '\n'.join(l['text'] for l in lines)
            period = re.search(r'du (\d{2}/\d{2}/\d{4}) au (\d{2}/\d{2}/\d{4})', text)
            if period:
                this_start, this_end = [datetime.strptime(v, '%d/%m/%Y').date() for v in period.groups()]
                if end and (start, end) != (this_start, this_end):
                    raise ValueError('Plusieurs périodes dans le PDF : séparez les états.')
                start, end = this_start, this_end
            if not text.strip():
                issues.append(f'Page {page.page_number} sans texte : PDF scanné non pris en charge.')
                continue
            account, bounds, last = None, None, None
            for line in lines:
                t = line['text']
                if t.startswith('Compte :'):
                    account = re.match(r'Compte\s*:\s*(\S+)', t).group(1)
                    bounds, last = None, None
                    continue
                if 'Montant HT' in t and 'Antérieur' in t:
                    words = [w for w in page.extract_words() if abs(w['top']-line['top']) < 2]
                    pos = {w['text']: w['x0'] for w in words}
                    bounds = [pos['Montant']-8, pos['Date']-8, pos['Taux']-3,
                              pos['Antérieur']-4, pos['Exercice']-12,
                              pos['Total']-12, pos['Résiduelle']-8, pos['Cession']-4, page.width]
                    continue
                if bounds is None or account is None:
                    continue
                def cell(i):
                    return ''.join(c['text'] for c in line['chars'] if bounds[i] <= (c['x0']+c['x1'])/2 < bounds[i+1]).strip()
                if t.startswith('Totaux compte'):
                    try:
                        totals.append({'Compte': account, **dict(zip(MONEY, [amount(cell(i)) for i in [0,3,4,5,6]]))})
                    except Exception as exc:
                        issues.append(f'Total illisible page {page.page_number} : {exc}')
                    bounds, last = None, None
                    continue
                match = re.match(r'^(\d{5})\s+(\d{3})\s+', t)
                if match:
                    try:
                        if not end:
                            raise ValueError('Période absente')
                        left = ' '.join(w['text'] for w in page.extract_words() if abs(w['top']-line['top']) < 2 and (w['x0']+w['x1'])/2 < bounds[0])
                        label = re.sub(r'^\d{5}\s+\d{3}\s*', '', left)
                        dm = re.fullmatch(r'(\d{6})\s*([A-Z])', cell(1))
                        if not dm:
                            raise ValueError(f'Date/mode non reconnus : {cell(1)}')
                        d, mode = dm.groups()
                        if mode not in ['L','N','D']:
                            raise ValueError(f'Mode {mode} non pris en charge')
                        row = {'Référence': match[1]+'-'+match[2], 'Compte': account, 'Libellé': label,
                               'Date acquisition': date6(d, end.year), 'Mode': mode, 'Taux': amount(cell(2)),
                               **dict(zip(MONEY, [amount(cell(i)) for i in [0,3,4,5,6]])),
                               'Date cession': date6(cell(7), end.year), 'Page': page.page_number}
                        rows.append(row)
                        last = row
                    except Exception as exc:
                        issues.append(f'Page {page.page_number}, {match[1]} : {exc}')
                        last = None
                elif last:
                    # Les lignes fournisseurs commencent à gauche du libellé (ex. 08BUL).
                    label_x = bounds[0] * 0.24
                    if line['x0'] >= label_x and line['x1'] < bounds[0]:
                        last['Libellé'] += ' ' + t
                    elif re.match(r'^\d', t) and line['x1'] > bounds[0]:
                        issues.append(f'Ligne numérique non reconnue page {page.page_number} : {t}')
            if 'No Immo' in text and not any(r['Page'] == page.page_number for r in rows):
                issues.append(f'Aucune immobilisation extraite page {page.page_number}.')
    if not rows:
        raise ValueError('Aucune immobilisation reconnue. Utilisez un PDF texte « Etat des dotations B.I.C. - B.A. », pas un scan.')
    df = pd.DataFrame(rows)
    if df['Référence'].duplicated().any():
        issues.append('Références en doublon : vérifier que le PDF ne contient pas plusieurs dossiers ou des pages répétées.')
    for _, r in df.iterrows():
        if abs(r['Antérieur'] + r['Exercice'] - r['Total']) > .011 or abs(r['Montant HT'] - r['Total'] - r['VNC']) > .011:
            issues.append(f"{r['Référence']} : montants incohérents (brut, amortissements, VNC).")
    checks = []
    for total in totals:
        part = df[df['Compte'] == total['Compte']]
        for key in MONEY:
            got = round(part[key].sum(), 2)
            checks.append({'Compte': total['Compte'], 'Rubrique': key, 'PDF': total[key], 'Extrait': got, 'Écart': round(got-total[key],2)})
    for account in df['Compte'].unique():
        if not any(t['Compte'] == account for t in totals):
            issues.append(f'Compte {account} : total PDF non trouvé, cadrage indisponible.')
    return df, pd.DataFrame(checks), issues, start, end

def prepare_import(df, start, end, after=True):
    reprise = end + timedelta(days=1) if after else start
    values = []
    for _, r in df.iterrows():
        # Un taux linéaire arrondi permet une estimation de la durée en mois.
        months = round(1200/r['Taux']) if r['Mode']=='L' and r['Taux']>0 else None
        values.append({'Inclure': True, 'Référence': r['Référence'], 'Libellé': r['Libellé'],
                       "Compte d’immobilisation": r['Compte'], "Date d’acquisition": r['Date acquisition'],
                       "Date de début d’amortissement": r['Date acquisition'], "Valeur brute": r['Montant HT'],
                       "Type d’amortissement": {'L':'Linéaire','N':'Non amortissable','D':'Dégressif'}[r['Mode']],
                       "Durée (mois)": months, "Valeur amortie": r['Total'] if after else r['Antérieur'],
                       "Exercice de reprise": reprise.strftime('%d/%m/%Y'), "Date de cession": r['Date cession']})
    return pd.DataFrame(values)

def csv_bytes(df, sep=';'):
    return df.to_csv(index=False, sep=sep, decimal=',', float_format='%.2f', lineterminator='\n').encode('utf-8-sig')
