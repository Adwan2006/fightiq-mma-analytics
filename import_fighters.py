from pathlib import Path
import csv
import io
import re
import sqlite3
import requests


DATABASE = str(Path(__file__).with_name("fightiq.db"))

FIGHTERS_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "rfordatascience/tidytuesday/main/"
    "data/2026/2026-07-07/"
    "ufcstats_data.csv"
)

FIGHTS_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "rfordatascience/tidytuesday/main/"
    "data/2026/2026-07-07/"
    "ufc_fights.csv"
)


def connect_database():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def slugify(name):
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def clean_text(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.upper() in [
        "NA",
        "N/A",
        "NULL",
        "NONE"
    ]:
        return ""

    return value


def clean_number(value):
    value = clean_text(value)

    if not value:
        return 0.0

    value = value.replace("%", "")

    try:
        return float(value)
    except ValueError:
        return 0.0


def clean_integer(value):
    return int(clean_number(value))


def clean_percentage(value):
    value = clean_text(value)

    if not value:
        return 0.0

    value = value.replace("%", "")

    try:
        number = float(value)

        if 0 < number <= 1:
            number *= 100

        return round(number, 1)

    except ValueError:
        return 0.0


def determine_weight_class(weight):
    weight_value = clean_number(weight)

    if weight_value <= 0:
        return "Unknown"

    if weight_value <= 115:
        return "Strawweight"

    if weight_value <= 125:
        return "Flyweight"

    if weight_value <= 135:
        return "Bantamweight"

    if weight_value <= 145:
        return "Featherweight"

    if weight_value <= 155:
        return "Lightweight"

    if weight_value <= 170:
        return "Welterweight"

    if weight_value <= 185:
        return "Middleweight"

    if weight_value <= 205:
        return "Light Heavyweight"

    return "Heavyweight"


def format_height_inches(value):
    value = clean_text(value)

    if not value:
        return ""

    # If already formatted like 5' 11"
    if "'" in value:
        return value

    try:
        inches = float(value)
    except ValueError:
        return value

    total_inches = int(round(inches))

    feet = total_inches // 12
    remaining_inches = total_inches % 12

    return f"{feet}' {remaining_inches}\""


def format_inches(value):
    value = clean_text(value)

    if not value:
        return ""

    # If already contains inch mark
    if '"' in value:
        return value

    try:
        inches = float(value)
    except ValueError:
        return value

    if inches.is_integer():
        return f'{int(inches)}"'

    return f'{round(inches, 1)}"'


def format_weight(value):
    value = clean_text(value)

    if not value:
        return ""

    # If already formatted
    if "lb" in value.lower():
        return value

    try:
        weight = float(value)
    except ValueError:
        return value

    if weight.is_integer():
        return f"{int(weight)} lb"

    return f"{round(weight, 1)} lb"


def download_csv(url, label):
    print(f"Downloading {label}...")

    response = requests.get(
        url,
        timeout=90
    )

    response.raise_for_status()

    print(f"{label} downloaded.")

    return response.text


def recreate_database():
    connection = connect_database()
    cursor = connection.cursor()


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fighters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            slug TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,
            record TEXT,

            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            no_contests INTEGER DEFAULT 0,

            weight_class TEXT,

            height TEXT,
            weight TEXT,
            reach TEXT,
            stance TEXT,
            date_of_birth TEXT,

            significant_strikes_per_minute REAL DEFAULT 0,
            striking_accuracy REAL DEFAULT 0,

            significant_strikes_absorbed_per_minute REAL DEFAULT 0,
            striking_defense REAL DEFAULT 0,

            takedown_average REAL DEFAULT 0,
            takedown_accuracy REAL DEFAULT 0,
            takedown_defense REAL DEFAULT 0,

            submission_average REAL DEFAULT 0,

            image_url TEXT,
            image_page_url TEXT,
            image_license TEXT,
            image_artist TEXT,
            image_checked INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            fight_url TEXT UNIQUE,

            event_name TEXT,
            fight_date TEXT,
            location TEXT,

            fighter1_name TEXT,
            fighter1_result TEXT,

            fighter2_name TEXT,
            fighter2_result TEXT,

            weight_class TEXT,

            method TEXT,
            round INTEGER,
            fight_time TEXT,
            time_format TEXT,

            referee TEXT,
            judging_details TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fights_fighter1
        ON fights(fighter1_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fights_fighter2
        ON fights(fighter2_name)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_fights_date
        ON fights(fight_date)
    """)

    connection.commit()
    connection.close()


def import_fighters():
    csv_text = download_csv(
        FIGHTERS_CSV_URL,
        "fighter dataset"
    )

    reader = csv.DictReader(
        io.StringIO(csv_text)
    )

    connection = connect_database()
    cursor = connection.cursor()

    imported = 0
    slug_counts = {}

    for row in reader:
        name = clean_text(
            row.get("name")
        )

        if not name:
            continue

        base_slug = slugify(name)

        if base_slug in slug_counts:
            slug_counts[base_slug] += 1

            slug = (
                f"{base_slug}-"
                f"{slug_counts[base_slug]}"
            )
        else:
            slug_counts[base_slug] = 1
            slug = base_slug

        wins = clean_integer(
            row.get("wins")
        )

        losses = clean_integer(
            row.get("losses")
        )

        draws = clean_integer(
            row.get("draws")
        )

        no_contests = clean_integer(
            row.get("nc")
        )

        record = (
            f"{wins}-"
            f"{losses}-"
            f"{draws}"
        )

        raw_height = row.get("height")
        raw_weight = row.get("weight")
        raw_reach = row.get("reach")

        height = format_height_inches(
            raw_height
        )

        weight = format_weight(
            raw_weight
        )

        reach = format_inches(
            raw_reach
        )

        weight_class = determine_weight_class(
            raw_weight
        )

        stance = clean_text(
            row.get("stance")
        )

        date_of_birth = clean_text(
            row.get("dob")
        )

        slpm = clean_number(
            row.get("s_lp_m")
        )

        striking_accuracy = clean_percentage(
            row.get("str_acc")
        )

        sapm = clean_number(
            row.get("s_ap_m")
        )

        striking_defense = clean_percentage(
            row.get("str_def")
        )

        takedown_average = clean_number(
            row.get("td_avg")
        )

        takedown_accuracy = clean_percentage(
            row.get("td_acc")
        )

        takedown_defense = clean_percentage(
            row.get("td_def")
        )

        submission_average = clean_number(
            row.get("sub_avg")
        )

        cursor.execute("""
            INSERT INTO fighters (
                slug,
                name,
                record,

                wins,
                losses,
                draws,
                no_contests,

                weight_class,

                height,
                weight,
                reach,
                stance,
                date_of_birth,

                significant_strikes_per_minute,
                striking_accuracy,

                significant_strikes_absorbed_per_minute,
                striking_defense,

                takedown_average,
                takedown_accuracy,
                takedown_defense,

                submission_average,

                image_url,
                image_page_url,
                image_license,
                image_artist,
                image_checked
            )

            VALUES (
                ?,
                ?, ?,
                ?, ?, ?, ?,
                ?,
                ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                0
            )
            ON CONFLICT(slug) DO UPDATE SET
                name = excluded.name,
                record = excluded.record,
                wins = excluded.wins,
                losses = excluded.losses,
                draws = excluded.draws,
                no_contests = excluded.no_contests,
                weight_class = excluded.weight_class,
                height = excluded.height,
                weight = excluded.weight,
                reach = excluded.reach,
                stance = excluded.stance,
                date_of_birth = excluded.date_of_birth,
                significant_strikes_per_minute = excluded.significant_strikes_per_minute,
                striking_accuracy = excluded.striking_accuracy,
                significant_strikes_absorbed_per_minute = excluded.significant_strikes_absorbed_per_minute,
                striking_defense = excluded.striking_defense,
                takedown_average = excluded.takedown_average,
                takedown_accuracy = excluded.takedown_accuracy,
                takedown_defense = excluded.takedown_defense,
                submission_average = excluded.submission_average
        """, (
            slug,
            name,
            record,

            wins,
            losses,
            draws,
            no_contests,

            weight_class,

            height,
            weight,
            reach,
            stance,
            date_of_birth,

            slpm,
            striking_accuracy,

            sapm,
            striking_defense,

            takedown_average,
            takedown_accuracy,
            takedown_defense,

            submission_average
        ))

        imported += 1

    connection.commit()
    connection.close()

    return imported


def import_fights():
    csv_text = download_csv(
        FIGHTS_CSV_URL,
        "fight history dataset"
    )

    reader = csv.DictReader(
        io.StringIO(csv_text)
    )

    connection = connect_database()
    cursor = connection.cursor()

    imported = 0

    for row in reader:
        fight_url = clean_text(
            row.get("fight_url")
        )

        fighter1_name = clean_text(
            row.get("f1_name")
        )

        fighter2_name = clean_text(
            row.get("f2_name")
        )

        if (
            not fighter1_name
            or not fighter2_name
        ):
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO fights (
                fight_url,

                event_name,
                fight_date,
                location,

                fighter1_name,
                fighter1_result,

                fighter2_name,
                fighter2_result,

                weight_class,

                method,
                round,
                fight_time,
                time_format,

                referee,
                judging_details
            )

            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?, ?,
                ?, ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
        """, (
            fight_url,

            clean_text(
                row.get("event_name")
            ),

            clean_text(
                row.get("date")
            ),

            clean_text(
                row.get("location")
            ),

            fighter1_name,

            clean_text(
                row.get("f1_result")
            ),

            fighter2_name,

            clean_text(
                row.get("f2_result")
            ),

            clean_text(
                row.get("weight_class")
            ),

            clean_text(
                row.get("method")
            ),

            clean_integer(
                row.get("round")
            ),

            clean_text(
                row.get("time")
            ),

            clean_text(
                row.get("time_format")
            ),

            clean_text(
                row.get("referee")
            ),

            clean_text(
                row.get("judging_details")
            )
        ))

        imported += 1

    connection.commit()
    connection.close()

    return imported


def main():
    print()
    print("FightIQ data pipeline started.")
    print()

    recreate_database()

    fighter_count = import_fighters()

    print()
    print(
        "Fighters imported:",
        fighter_count
    )

    print()

    fight_count = import_fights()

    print()
    print(
        "Fights imported:",
        fight_count
    )

    print()
    print("------------------------------")
    print("FightIQ database ready.")
    print("------------------------------")
    print()


if __name__ == "__main__":
    main()