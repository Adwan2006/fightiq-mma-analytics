"""Idempotent, transactional historical UFC CSV import; leaves existing tables intact."""
import argparse
import csv
import hashlib
import io
import math
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from betting import SOURCE_URL, ensure_schema, name_key, probability

DATABASE = Path(__file__).with_name('fightiq.db')


def ingest(database, csv_text, source=SOURCE_URL):
    reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
    required = {'r_fighter','b_fighter','r_odds','b_odds','date','winner','weight_class'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('CSV is missing required columns: '+', '.join(sorted(required-set(reader.fieldnames or []))))
    rows, read = {}, 0
    for row in reader:
        read += 1
        red, blue = row['r_fighter'].strip(), row['b_fighter'].strip()
        day = date.fromisoformat(row['date'].strip()).isoformat()
        if not name_key(red) or not name_key(blue) or name_key(red)==name_key(blue):
            raise ValueError(f'Invalid fighter names on CSV row {read+1}')
        winner = row['winner'].strip()
        if winner not in ('Red','Blue','Draw','No Contest'):
            raise ValueError(f'Unknown result {winner!r} on CSV row {read+1}')
        odds = [float(row[k]) if probability(row[k]) is not None else None for k in ('r_odds','b_odds')]
        division = row['weight_class'].strip() or 'Unknown'
        if row.get('gender','').upper()=='FEMALE' and not division.lower().startswith("women"):
            division = "Women's " + division
        key = day+'|'+ '|'.join(sorted([name_key(red),name_key(blue)]))
        values = (key, day, red, blue, name_key(red), name_key(blue), *odds, winner, division, row.get('finish',''), source)
        if key in rows and rows[key] != values:
            raise ValueError(f'Conflicting duplicate bout on CSV row {read+1}')
        rows[key] = values
    if not rows:
        raise ValueError('CSV contains no bouts; database left unchanged')
    with closing(sqlite3.connect(database)) as connection:
        ensure_schema(connection)
        with connection:
            connection.executemany('''INSERT INTO historical_odds VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(bout_key) DO UPDATE SET fight_date=excluded.fight_date,
                red_name=excluded.red_name, blue_name=excluded.blue_name,
                red_key=excluded.red_key, blue_key=excluded.blue_key,
                red_odds=excluded.red_odds, blue_odds=excluded.blue_odds,
                winner=excluded.winner, division=excluded.division,
                finish=excluded.finish, source_url=excluded.source_url''', rows.values())
            connection.execute('INSERT INTO odds_imports(imported_at,source_url,sha256,rows_read,rows_stored) VALUES (?,?,?,?,?)',
                (datetime.now(timezone.utc).isoformat(), source, hashlib.sha256(csv_text.encode()).hexdigest(), read, len(rows)))
    return dict(rows_read=read, unique_bouts=len(rows), duplicates=read-len(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, help='Local CSV in TidyTuesday format; otherwise download the public dataset')
    parser.add_argument('--database', type=Path, default=DATABASE)
    args = parser.parse_args()
    if args.csv:
        text = args.csv.read_text(encoding='utf-8-sig')
        source = str(args.csv.resolve())
    else:
        response = requests.get(SOURCE_URL, timeout=90)
        response.raise_for_status()
        text, source = response.text, SOURCE_URL
    print(ingest(args.database, text, source))


if __name__ == '__main__':
    main()
