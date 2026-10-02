"""Historical moneyline analytics; no predictions or betting recommendations."""
import math
import re
import sqlite3
import unicodedata
from collections import defaultdict
from contextlib import closing

SOURCE_URL = 'https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2026/2026-07-07/ultimate_ufc_dataset.csv'
SOURCE_PAGE = 'https://github.com/rfordatascience/tidytuesday/tree/main/data/2026/2026-07-07'


def name_key(name):
    text = unicodedata.normalize('NFKD', name or '')
    return re.sub(r'[^a-z0-9]', '', text.encode('ascii', 'ignore').decode().lower())


def probability(odds):
    try:
        odds = float(odds)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(odds) or abs(odds) < 100:
        return None
    return -odds / (100 - odds) if odds < 0 else 100 / (100 + odds)


def ensure_schema(connection):
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS historical_odds (
            bout_key TEXT PRIMARY KEY, fight_date TEXT NOT NULL,
            red_name TEXT NOT NULL, blue_name TEXT NOT NULL,
            red_key TEXT NOT NULL, blue_key TEXT NOT NULL,
            red_odds REAL, blue_odds REAL, winner TEXT NOT NULL,
            division TEXT NOT NULL, finish TEXT, source_url TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_odds_red ON historical_odds(red_key);
        CREATE INDEX IF NOT EXISTS idx_odds_blue ON historical_odds(blue_key);
        CREATE TABLE IF NOT EXISTS odds_imports (
            id INTEGER PRIMARY KEY, imported_at TEXT NOT NULL,
            source_url TEXT NOT NULL, sha256 TEXT NOT NULL,
            rows_read INTEGER NOT NULL, rows_stored INTEGER NOT NULL
        );
    ''')


def load_bouts(database):
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='historical_odds'").fetchone():
            return [], None
        rows = [dict(row) for row in connection.execute('SELECT * FROM historical_odds ORDER BY fight_date DESC')]
        meta = connection.execute('SELECT * FROM odds_imports ORDER BY id DESC LIMIT 1').fetchone()
    for row in rows:
        rp, bp = probability(row['red_odds']), probability(row['blue_odds'])
        row['status'] = ('missing odds' if rp is None or bp is None else
                         'tied odds' if math.isclose(rp, bp) else
                         'non-decisive result' if row['winner'] not in ('Red', 'Blue') else 'eligible')
        row['favorite'] = 'Red' if rp is not None and bp is not None and rp > bp else 'Blue'
        row['upset'] = row['status'] == 'eligible' and row['winner'] != row['favorite']
    return rows, dict(meta) if meta else None


def rate(wins, total):
    return round(100 * wins / total, 1) if total else None


def summary(rows):
    eligible = [r for r in rows if r['status'] == 'eligible']
    upsets = sum(r['upset'] for r in eligible)
    return dict(total=len(rows), eligible=len(eligible), underdog_wins=upsets,
                underdog_losses=len(eligible)-upsets, favorite_wins=len(eligible)-upsets,
                favorite_losses=upsets, upset_rate=rate(upsets, len(eligible)),
                excluded=len(rows)-len(eligible),
                missing=sum(r['status']=='missing odds' for r in rows),
                tied=sum(r['status']=='tied odds' for r in rows),
                non_decisive=sum(r['status']=='non-decisive result' for r in rows))


BUCKETS = ['≤ -500', '-499 to -300', '-299 to -200', '-199 to -100', '+100 to +199', '+200 to +299', '+300 to +499', '≥ +500']


def bucket(odds):
    if odds < 0:
        return BUCKETS[0 if odds <= -500 else 1 if odds <= -300 else 2 if odds <= -200 else 3]
    return BUCKETS[4 if odds < 200 else 5 if odds < 300 else 6 if odds < 500 else 7]


def dashboard(rows):
    eligible = [r for r in rows if r['status']=='eligible']
    buckets = {label: dict(label=label, wins=0, total=0) for label in BUCKETS}
    divisions, years = defaultdict(list), defaultdict(list)
    for row in eligible:
        divisions[row['division']].append(row)
        years[row['fight_date'][:4]].append(row)
        for side, color in [('red', 'Red'), ('blue', 'Blue')]:
            group = buckets[bucket(row[side+'_odds'])]
            group['total'] += 1
            group['wins'] += row['winner'] == color
    for group in buckets.values():
        group['losses'] = group['total']-group['wins']
        group['rate'] = rate(group['wins'], group['total'])
    grouped = lambda groups: [dict(label=k, **summary(v)) for k,v in sorted(groups.items())]
    return dict(summary=summary(rows), buckets=list(buckets.values()), divisions=grouped(divisions), years=grouped(years))


def fighter_context(rows, fighter):
    key = name_key(fighter['name'])
    history = []
    for row in rows:
        if key not in (row['red_key'], row['blue_key']):
            continue
        side = 'red' if key == row['red_key'] else 'blue'
        color = side.title()
        role = ('Favorite' if color == row['favorite'] else 'Underdog') if row['status']=='eligible' else 'Excluded'
        history.append(dict(row, role=role, odds=row[side+'_odds'],
                            opponent=row['blue_name' if side=='red' else 'red_name'],
                            won=row['winner']==color,
                            result=('Win' if row['winner']==color else 'Loss') if row['winner'] in ('Red','Blue') else row['winner']))
    records = []
    for role in ('Favorite', 'Underdog'):
        bouts = [r for r in history if r['role']==role]
        wins = sum(r['won'] for r in bouts)
        records.append(dict(role=role, wins=wins, losses=len(bouts)-wins, total=len(bouts), rate=rate(wins,len(bouts))))
    upsets = [r for r in history if r['role']=='Underdog' and r['won']]
    biggest = min(upsets, key=lambda r: probability(r['odds'])) if upsets else None
    return dict(records=records, biggest=biggest, history=history, excluded=sum(r['role']=='Excluded' for r in history))


def metric_notes(fighter):
    # Explicit descriptive thresholds. Legacy importer represents unknown values as zero.
    rules = [
        ('significant_strikes_per_minute','Striking volume',5,2.5,'landed/min',True),
        ('significant_strikes_absorbed_per_minute','Strikes absorbed',2.5,4.5,'absorbed/min',False),
        ('striking_defense','Striking defense',60,45,'%',True),
        ('takedown_defense','Takedown defense',75,50,'%',True),
        ('takedown_average','Takedown activity',2,0.5,'/15 min',True),
        ('submission_average','Submission attempts',1,0.2,'/15 min',True),
    ]
    strengths, weaknesses = [], []
    for field, label, high, low, unit, higher_better in rules:
        value = fighter[field]
        if value is None or value <= 0 or not math.isfinite(value):
            continue
        strong = value >= high if higher_better else value <= high
        weak = value <= low if higher_better else value >= low
        text = f'{label}: {value:g} {unit} (descriptive threshold {"≥" if higher_better == strong else "≤"} {high if strong else low:g}).'
        if strong: strengths.append(text)
        elif weak: weaknesses.append(text)
    return dict(strengths=strengths, weaknesses=weaknesses)
