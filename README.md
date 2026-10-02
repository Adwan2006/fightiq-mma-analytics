# FightIQ

FightIQ is a full-stack MMA analytics platform built with Python, Flask, SQLite, HTML, CSS, and JavaScript.

It combines fighter statistics, UFC fight history, head-to-head comparisons, historical betting analytics, charts, and data pipelines in one project.

## Screenshots

### Home
![FightIQ Home](screenshots/home.png)

### Fighter Profile
![Fighter Profile](screenshots/fighter-profile.png)

### Compare
![FightIQ Compare](screenshots/compare.png)

### Betting Analytics
![FightIQ Betting Analytics](screenshots/betting.png)

## Features

- Searchable MMA fighter database
- Fighter profiles with career records and physical attributes
- Fighter photos from Wikimedia/Wikidata when available
- Striking statistics
- Grappling statistics
- UFC fight history
- Head-to-head fighter comparison
- Historical betting analytics
- Favorite vs underdog performance
- Historical upset rates
- Odds bucket analysis
- Division-based betting analytics
- Fighter-specific betting history
- Descriptive strengths and weaknesses
- Responsive dark UI
- SQLite database
- Python ETL/data ingestion scripts
- Automated tests

## Tech Stack

### Backend

- Python
- Flask
- SQLite
- Requests

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2

### Data Engineering

- CSV ingestion
- HTTP data retrieval
- Data cleaning
- Data transformation
- SQLite loading
- Historical odds processing
- Fighter and fight record normalization

## Project Structure

```text
fightiq-mma-analytics/
├── app.py
├── betting.py
├── import_fighters.py
├── import_odds.py
├── requirements.txt
├── README.md
├── data/
│   └── ultimate_ufc_dataset.csv
├── screenshots/
│   ├── home.png
│   ├── fighter-profile.png
│   ├── compare.png
│   └── betting.png
├── static/
│   └── style.css
├── templates/
│   ├── analytics.html
│   ├── base.html
│   ├── betting.html
│   ├── compare.html
│   ├── fighter_profile.html
│   ├── fighters.html
│   ├── index.html
│   ├── _fighter_betting.html
│   └── _metric_notes.html
└── tests/
```

## Fighter Analytics

Each fighter profile can include:

- Career record
- Height
- Weight
- Reach
- Stance
- Date of birth
- Significant strikes landed per minute
- Significant strikes absorbed per minute
- Striking accuracy
- Strike defense
- Takedown average
- Takedown accuracy
- Takedown defense
- Submission average
- UFC fight history
- Historical favorite/underdog performance
- Descriptive strengths and weaknesses

## Fighter Comparison

FightIQ allows users to search for two fighters and compare them side by side.

Comparison metrics include:

- Record
- Height
- Reach
- Stance
- Striking accuracy
- Striking volume
- Strike defense
- Takedown average
- Takedown accuracy
- Takedown defense
- Submission activity
- Historical betting context

## Historical Betting Analytics

FightIQ includes descriptive historical betting analytics such as:

- Favorite wins and losses
- Underdog wins and losses
- Historical upset rate
- Favorite win rate
- Underdog win rate
- Performance by odds range
- Division-based upset rates
- Fighter favorite/underdog history
- Historical odds trends

These statistics are historical analytics only and are not guarantees, predictions, or betting recommendations.

## Historical Betting Dataset

Source: TidyTuesday UFC data, July 7, 2026 — `ultimate_ufc_dataset.csv`.

The bundled snapshot contains historical UFC betting and fight data and is used for reproducible analysis.

Historical odds are analyzed using valid American moneylines. Favorite and underdog roles are determined using implied probability.

The betting section includes favorite win percentage, underdog upset percentage, win rates by odds range, division-level upset rates, fighter betting history, largest recorded historical upsets, and year-based trends.

The data is historical and should not be interpreted as live odds or future predictions.

## Data Sources

FightIQ uses publicly available MMA datasets containing fighter statistics, UFC fight history, and historical betting odds.

The project also uses Wikimedia/Wikidata for fighter images where available.

## Data Pipeline

```text
Public datasets / APIs
        ↓
Python ingestion scripts
        ↓
Cleaning and normalization
        ↓
SQLite database
        ↓
Flask backend
        ↓
Jinja templates
        ↓
FightIQ web interface
```

## Installation

Clone the repository:

```bash
git clone https://github.com/Adwan2006/fightiq-mma-analytics.git
```

Enter the project:

```bash
cd fightiq-mma-analytics
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Build or refresh fighter data:

```bash
python3 import_fighters.py
```

Import historical odds:

```bash
python3 import_odds.py
```

Or use the bundled snapshot:

```bash
python3 import_odds.py --csv data/ultimate_ufc_dataset.csv
```

Start FightIQ:

```bash
python3 app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Main Pages

- Home: `/`
- Fighters: `/fighters`
- Compare: `/compare`
- Analytics: `/analytics`
- Betting Analytics: `/betting`

## Testing

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Project Goals

FightIQ demonstrates practical skills in Python, data engineering, SQL, Flask backend development, ETL pipelines, analytics, frontend development, API integration, database design, testing, and Git/GitHub workflow.

## Disclaimer

Historical betting analytics in FightIQ are descriptive only.

They are not betting recommendations, guarantees, or predictions of future fight outcomes.

## Author

**Yousef Aladwan**

GitHub: https://github.com/Adwan2006