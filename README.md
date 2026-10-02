# FightIQ historical betting upgrade

The existing Flask app, dark styling, fighter photos and attribution, live search,
profiles, Compare, UFC fight history and analytics are retained. Historical odds
are stored separately in the same SQLite database.

## Run

From the upgraded original project:

```bash
cd /Users/yousefaladwan/Desktop/weather-data-pipeline/fightiq-mma-analytics
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Open http://127.0.0.1:5000/betting. The database already contains the imported
historical odds; no import is needed to view them. If port 5000 is occupied:

```bash
python3 -m flask --app app run --port 5055
```

Refresh historical odds from the public source:

```bash
python3 import_odds.py
```

Reimport the bundled, reproducible snapshot without a network connection:

```bash
python3 import_odds.py --csv data/ultimate_ufc_dataset.csv
```

Refresh the original fighter metrics and UFC fight history:

```bash
python3 import_fighters.py
```

This importer now creates missing tables and updates fighters by slug while
preserving existing IDs and cached photo fields. Existing fights and historical
odds remain intact. Refreshes add/update source records rather than deleting
records absent from a later source. The two importers are independent: run both
when refreshing both sources. The historical CSV command also accepts
`--database /absolute/path/to/another.db`.

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Changed files

- `app.py`: Betting route, template helpers and formatting; database path now
  resolves beside the app regardless of the launch directory.
- `betting.py` (new): normalization, American odds validation, role assignment,
  exclusions, overall/year/division/bucket analytics, fighter history and
  descriptive metric thresholds.
- `import_odds.py` (new): validated, transactional, idempotent odds ingestion,
  duplicate detection and source/hash/import metadata.
- `import_fighters.py`: additive schema creation and fighter upserts preserving
  cached photos and IDs; existing importer entry point retained.
- `templates/base.html`: Betting navbar link.
- `templates/betting.html` (new): year/division filters, win/loss summaries,
  accessible HTML/CSS charts and tables, sample counts and methodology.
- `templates/_fighter_betting.html` (new): favorite/underdog records, largest
  recorded upset and expandable historical odds/results.
- `templates/_metric_notes.html` (new): strengths and potential weaknesses based
  on imported career metrics, with explicit editorial thresholds.
- `templates/fighter_profile.html`: adds both new sections after existing content.
- `templates/compare.html`: adds each fighter's historical context and metrics.
- `static/style.css`: additive styling for the new sections and mobile layout.
- `tests/test_betting.py` (new): calculation boundaries, exclusions, idempotency,
  malformed/conflicting imports, name matching, photo/ID preservation and routes.
- `data/ultimate_ufc_dataset.csv` (new): original public source snapshot.
- `fightiq.db`: adds `historical_odds` and `odds_imports` with indexes; existing
  fighter and fight rows retained.
- `README.md` (new): run commands, methodology and validation.

## Source and methodology

Source: [TidyTuesday UFC data, July 7, 2026](https://github.com/rfordatascience/tidytuesday/tree/main/data/2026/2026-07-07),
`ultimate_ufc_dataset.csv`. The supplied snapshot has 7,177 unique bouts from
2010-03-21 through 2026-03-28. The first and last years are partial coverage.
It is a historical snapshot, not live odds or current UFC results. The source's
specific bookmaker and opening/closing timing are not verified.

Favorite = higher implied probability using both valid American moneylines:
negative −a => a/(a+100); positive +a => 100/(a+100). Odds must be finite with
absolute value >= 100. Both-negative and both-positive lines are supported.
Equal implied probabilities (including −100/+100) are tied prices.

Eligible bouts have two valid unequal odds and a Red or Blue winner. Exclusions
are applied in order: missing/invalid odds, tied prices, non-decisive result.
The snapshot has 253, 120 and 8 in these groups respectively. Rates use 6,796
eligible bouts: 4,524 favorite wins and 2,272 underdog wins (33.4% upsets).
Every favorite loss equals one underdog win. Bucket charts use fighter
appearances, two per eligible bout, while year/division charts use bouts.
Women's divisions are kept separate using source gender. Filters affect all
Betting page summaries and charts together.

Fighter matching normalizes case, accents and punctuation; unmatched spelling
variants/aliases may reduce coverage. A fighter's biggest upset is the eligible
underdog win with the lowest implied probability in the available dataset.
A zero sample is shown as N/A, never a 0% measured rate. Tables expose the
numeric chart values without requiring a chart library or external CDN.

Descriptive strengths and potential weaknesses use fixed editorial thresholds
shown with each note. These are career metrics, not necessarily values known
before a historical matchup. They are not empirically validated prediction
rules. Legacy zero values are omitted because the original importer represents
both missing and genuine zero values as zero. These sections make no claims
about future wins or profitability.

## Validation

Eight automated tests pass, including all existing route types and the new
Betting page; external photo lookups are mocked in automated route tests.
The original 4,504 fighters and 8,736 fight records were compared field by field
against the working copy and were identical before applying the upgrade.
Browser checks cover live autocomplete, comparison, profile history, Betting
filters and dark layout. Photo rendering still depends on Wikimedia availability.
