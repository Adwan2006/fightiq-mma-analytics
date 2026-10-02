from flask import (
    Flask,
    render_template,
    request,
    abort,
    jsonify
)

from pathlib import Path
from flask import g
import betting as betting_analytics
import sqlite3
import requests
import re


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

DATABASE = str(Path(__file__).with_name("fightiq.db"))

WIKIDATA_API = (
    "https://www.wikidata.org/w/api.php"
)

COMMONS_API = (
    "https://commons.wikimedia.org/w/api.php"
)

HEADERS = {
    "User-Agent": (
        "FightIQ-MMA-Analytics/1.0 "
        "Educational Portfolio Project"
    )
}


# =========================================================
# DATABASE
# =========================================================

def connect_database():
    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


# =========================================================
# HELPERS
# =========================================================

def strip_html(value):
    if not value:
        return ""

    return re.sub(
        r"<[^>]+>",
        "",
        str(value)
    ).strip()


def normalize_name(value):
    if not value:
        return ""

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9 ]",
        "",
        value
    )

    return " ".join(
        value.split()
    )


def display_fight_time(value):
    if not value:
        return ""

    value = value.strip()

    # Dataset values look like:
    # 3M 25S
    # 15S
    # 5M 0S

    minutes_match = re.search(
        r"(\d+)M",
        value
    )

    seconds_match = re.search(
        r"(\d+)S",
        value
    )

    minutes = (
        int(minutes_match.group(1))
        if minutes_match
        else 0
    )

    seconds = (
        int(seconds_match.group(1))
        if seconds_match
        else 0
    )

    return (
        f"{minutes}:{seconds:02d}"
    )


# =========================================================
# WIKIDATA
# =========================================================

def search_wikidata_fighter(
    fighter_name
):
    try:
        response = requests.get(
            WIKIDATA_API,
            params={
                "action":
                    "wbsearchentities",

                "search":
                    fighter_name,

                "language":
                    "en",

                "uselang":
                    "en",

                "type":
                    "item",

                "limit":
                    10,

                "format":
                    "json"
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        results = (
            response
            .json()
            .get(
                "search",
                []
            )
        )

    except Exception as error:
        print(
            "Wikidata search failed:",
            fighter_name,
            error
        )

        return None

    if not results:
        return None

    target_name = normalize_name(
        fighter_name
    )

    fighter_keywords = [
        "mixed martial artist",
        "mixed martial arts",
        "mma fighter",
        "martial artist",
        "ufc fighter",
        "professional fighter",
        "kickboxer",
        "boxer"
    ]

    for result in results:
        label = normalize_name(
            result.get(
                "label",
                ""
            )
        )

        description = (
            result.get(
                "description",
                ""
            )
            or ""
        ).lower()

        if (
            label == target_name
            and any(
                keyword in description
                for keyword
                in fighter_keywords
            )
        ):
            return result.get(
                "id"
            )

    for result in results:
        description = (
            result.get(
                "description",
                ""
            )
            or ""
        ).lower()

        if any(
            keyword in description
            for keyword
            in fighter_keywords
        ):
            return result.get(
                "id"
            )

    for result in results:
        label = normalize_name(
            result.get(
                "label",
                ""
            )
        )

        if label == target_name:
            return result.get(
                "id"
            )

    return None


def get_wikidata_image_filename(
    entity_id
):
    if not entity_id:
        return None

    try:
        response = requests.get(
            WIKIDATA_API,
            params={
                "action":
                    "wbgetentities",

                "ids":
                    entity_id,

                "props":
                    "claims",

                "format":
                    "json"
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        entity = (
            response
            .json()
            .get(
                "entities",
                {}
            )
            .get(
                entity_id,
                {}
            )
        )

        claims = entity.get(
            "claims",
            {}
        )

        image_claims = claims.get(
            "P18",
            []
        )

        if not image_claims:
            return None

        return (
            image_claims[0]
            .get(
                "mainsnak",
                {}
            )
            .get(
                "datavalue",
                {}
            )
            .get(
                "value"
            )
        )

    except Exception:
        return None


def get_commons_image(
    filename
):
    if not filename:
        return None

    try:
        response = requests.get(
            COMMONS_API,
            params={
                "action":
                    "query",

                "titles":
                    f"File:{filename}",

                "prop":
                    "imageinfo",

                "iiprop":
                    "url|extmetadata",

                "iiurlwidth":
                    900,

                "format":
                    "json",

                "formatversion":
                    2
            },
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()

        pages = (
            response
            .json()
            .get(
                "query",
                {}
            )
            .get(
                "pages",
                []
            )
        )

        if not pages:
            return None

        image_info = pages[0].get(
            "imageinfo",
            []
        )

        if not image_info:
            return None

        info = image_info[0]

        image_url = (
            info.get(
                "thumburl"
            )
            or
            info.get(
                "url"
            )
        )

        if not image_url:
            return None

        metadata = info.get(
            "extmetadata",
            {}
        )

        license_name = (
            metadata
            .get(
                "LicenseShortName",
                {}
            )
            .get(
                "value",
                ""
            )
        )

        artist = (
            metadata
            .get(
                "Artist",
                {}
            )
            .get(
                "value",
                ""
            )
        )

        return {
            "image_url":
                image_url,

            "image_page_url":
                info.get(
                    "descriptionurl",
                    ""
                ),

            "image_license":
                license_name,

            "image_artist":
                strip_html(
                    artist
                )
        }

    except Exception:
        return None


def fetch_fighter_image(
    fighter_name
):
    entity_id = (
        search_wikidata_fighter(
            fighter_name
        )
    )

    if not entity_id:
        return None

    filename = (
        get_wikidata_image_filename(
            entity_id
        )
    )

    if not filename:
        return None

    return get_commons_image(
        filename
    )


def ensure_fighter_image(
    fighter_id
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fighters
        WHERE id = ?
    """, (
        fighter_id,
    ))

    fighter = cursor.fetchone()

    if fighter is None:
        connection.close()
        return None

    if fighter["image_url"]:
        connection.close()
        return fighter

    if fighter["image_checked"]:
        connection.close()
        return fighter

    image_data = (
        fetch_fighter_image(
            fighter["name"]
        )
    )

    if image_data:
        cursor.execute("""
            UPDATE fighters

            SET
                image_url = ?,
                image_page_url = ?,
                image_license = ?,
                image_artist = ?,
                image_checked = 1

            WHERE id = ?
        """, (
            image_data[
                "image_url"
            ],

            image_data[
                "image_page_url"
            ],

            image_data[
                "image_license"
            ],

            image_data[
                "image_artist"
            ],

            fighter_id
        ))

    else:
        cursor.execute("""
            UPDATE fighters
            SET image_checked = 1
            WHERE id = ?
        """, (
            fighter_id,
        ))

    connection.commit()

    cursor.execute("""
        SELECT *
        FROM fighters
        WHERE id = ?
    """, (
        fighter_id,
    ))

    fighter = cursor.fetchone()

    connection.close()

    return fighter


# =========================================================
# FIGHTER QUERIES
# =========================================================

def get_fighter_count():
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM fighters
    """)

    count = cursor.fetchone()[0]

    connection.close()

    return count


def get_fighters(
    search="",
    division="",
    page=1,
    per_page=24
):
    connection = connect_database()
    cursor = connection.cursor()

    offset = (
        page - 1
    ) * per_page

    conditions = []
    parameters = []

    if search:
        conditions.append(
            "LOWER(name) LIKE ?"
        )

        parameters.append(
            f"%{search.lower()}%"
        )

    if division:
        conditions.append(
            "weight_class = ?"
        )

        parameters.append(
            division
        )

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    cursor.execute(
        f"""
        SELECT *
        FROM fighters
        {where_clause}
        ORDER BY name
        LIMIT ?
        OFFSET ?
        """,
        parameters + [
            per_page,
            offset
        ]
    )

    fighters = cursor.fetchall()

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM fighters
        {where_clause}
        """,
        parameters
    )

    total = cursor.fetchone()[0]

    connection.close()

    return fighters, total


def get_divisions():
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT DISTINCT
            weight_class

        FROM fighters

        WHERE
            weight_class != 'Unknown'

        ORDER BY
            weight_class
    """)

    divisions = [
        row[0]
        for row
        in cursor.fetchall()
    ]

    connection.close()

    return divisions


def get_fighter_by_slug(
    slug
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fighters
        WHERE slug = ?
    """, (
        slug,
    ))

    fighter = cursor.fetchone()

    connection.close()

    return fighter


def get_fighter_by_id(
    fighter_id
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fighters
        WHERE id = ?
    """, (
        fighter_id,
    ))

    fighter = cursor.fetchone()

    connection.close()

    return fighter


def get_fighter_by_name(
    name
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fighters

        WHERE
            LOWER(name)
            = LOWER(?)

        ORDER BY id

        LIMIT 1
    """, (
        name,
    ))

    fighter = cursor.fetchone()

    connection.close()

    return fighter


def search_fighters_live(
    query,
    limit=8
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fighters

        WHERE
            LOWER(name)
            LIKE ?

        ORDER BY
            CASE
                WHEN LOWER(name)
                = LOWER(?)
                THEN 0

                WHEN LOWER(name)
                LIKE LOWER(?)
                THEN 1

                ELSE 2
            END,

            name

        LIMIT ?
    """, (
        f"%{query.lower()}%",
        query,
        f"{query.lower()}%",
        limit
    ))

    fighters = cursor.fetchall()

    connection.close()

    return fighters


# =========================================================
# FIGHT HISTORY
# =========================================================

def get_fighter_fights(
    fighter_name
):
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM fights

        WHERE
            LOWER(fighter1_name)
            = LOWER(?)

            OR

            LOWER(fighter2_name)
            = LOWER(?)

        ORDER BY
            fight_date DESC
    """, (
        fighter_name,
        fighter_name
    ))

    rows = cursor.fetchall()

    connection.close()

    fights = []

    for row in rows:
        if (
            row["fighter1_name"].lower()
            == fighter_name.lower()
        ):
            result = (
                row["fighter1_result"]
            )

            opponent = (
                row["fighter2_name"]
            )
        else:
            result = (
                row["fighter2_result"]
            )

            opponent = (
                row["fighter1_name"]
            )

        fight = dict(row)

        fight["result"] = result

        fight["opponent"] = (
            opponent
        )

        fight["display_time"] = (
            display_fight_time(
                row["fight_time"]
            )
        )

        fights.append(
            fight
        )

    return fights


def get_fight_summary(
    fights
):
    wins = 0
    losses = 0
    draws = 0
    no_contests = 0

    ko_tko_wins = 0
    submission_wins = 0
    decision_wins = 0

    for fight in fights:
        result = (
            fight.get(
                "result",
                ""
            )
            or ""
        ).upper()

        method = (
            fight.get(
                "method",
                ""
            )
            or ""
        ).lower()

        if result == "W":
            wins += 1

            if (
                "ko/tko"
                in method
            ):
                ko_tko_wins += 1

            elif (
                "submission"
                in method
            ):
                submission_wins += 1

            elif (
                "decision"
                in method
            ):
                decision_wins += 1

        elif result == "L":
            losses += 1

        elif result == "D":
            draws += 1

        else:
            no_contests += 1

    return {
        "ufc_fights":
            len(fights),

        "ufc_wins":
            wins,

        "ufc_losses":
            losses,

        "ufc_draws":
            draws,

        "ufc_no_contests":
            no_contests,

        "ko_tko_wins":
            ko_tko_wins,

        "submission_wins":
            submission_wins,

        "decision_wins":
            decision_wins
    }


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():
    return render_template(
        "index.html",
        fighter_count=(
            get_fighter_count()
        )
    )


@app.route("/fighters")
def fighters():
    search = request.args.get(
        "search",
        ""
    ).strip()

    division = request.args.get(
        "division",
        ""
    )

    page = request.args.get(
        "page",
        1,
        type=int
    )

    if page < 1:
        page = 1

    per_page = 24

    fighter_list, total = (
        get_fighters(
            search=search,
            division=division,
            page=page,
            per_page=per_page
        )
    )

    if search:
        updated_fighters = []

        for fighter in fighter_list:
            updated = (
                ensure_fighter_image(
                    fighter["id"]
                )
            )

            updated_fighters.append(
                updated or fighter
            )

        fighter_list = (
            updated_fighters
        )

    total_pages = (
        total
        + per_page
        - 1
    ) // per_page

    return render_template(
        "fighters.html",

        fighters=fighter_list,

        search=search,

        division=division,

        divisions=(
            get_divisions()
        ),

        page=page,

        total_pages=(
            total_pages
        ),

        total=total
    )


@app.route(
    "/fighter/<slug>"
)
def fighter_profile(
    slug
):
    fighter = (
        get_fighter_by_slug(
            slug
        )
    )

    if fighter is None:
        abort(404)

    fighter = (
        ensure_fighter_image(
            fighter["id"]
        )
        or fighter
    )

    fight_history = (
        get_fighter_fights(
            fighter["name"]
        )
    )

    fight_summary = (
        get_fight_summary(
            fight_history
        )
    )

    return render_template(
        "fighter_profile.html",

        fighter=fighter,

        fight_history=(
            fight_history
        ),

        fight_summary=(
            fight_summary
        )
    )


@app.route(
    "/api/fighter-search"
)
def fighter_search_api():
    query = request.args.get(
        "q",
        ""
    ).strip()

    if len(query) < 2:
        return jsonify([])

    fighter_list = (
        search_fighters_live(
            query,
            limit=8
        )
    )

    results = []

    for fighter in fighter_list:
        fighter = (
            ensure_fighter_image(
                fighter["id"]
            )
            or fighter
        )

        results.append({
            "id":
                fighter["id"],

            "name":
                fighter["name"],

            "record":
                fighter["record"],

            "weight_class":
                fighter[
                    "weight_class"
                ],

            "image_url":
                fighter[
                    "image_url"
                ]
        })

    return jsonify(
        results
    )


@app.route("/compare")
def compare():
    fighter1_id = (
        request.args.get(
            "fighter1_id",
            type=int
        )
    )

    fighter2_id = (
        request.args.get(
            "fighter2_id",
            type=int
        )
    )

    fighter1_name = (
        request.args.get(
            "fighter1",
            ""
        ).strip()
    )

    fighter2_name = (
        request.args.get(
            "fighter2",
            ""
        ).strip()
    )

    fighter1 = None
    fighter2 = None

    if fighter1_id:
        fighter1 = (
            get_fighter_by_id(
                fighter1_id
            )
        )

    elif fighter1_name:
        fighter1 = (
            get_fighter_by_name(
                fighter1_name
            )
        )

    if fighter2_id:
        fighter2 = (
            get_fighter_by_id(
                fighter2_id
            )
        )

    elif fighter2_name:
        fighter2 = (
            get_fighter_by_name(
                fighter2_name
            )
        )

    if fighter1:
        fighter1 = (
            ensure_fighter_image(
                fighter1["id"]
            )
            or fighter1
        )

        fighter1_name = (
            fighter1["name"]
        )

    if fighter2:
        fighter2 = (
            ensure_fighter_image(
                fighter2["id"]
            )
            or fighter2
        )

        fighter2_name = (
            fighter2["name"]
        )

    return render_template(
        "compare.html",

        fighter1=fighter1,

        fighter2=fighter2,

        fighter1_name=(
            fighter1_name
        ),

        fighter2_name=(
            fighter2_name
        ),

        fighter1_id=(
            fighter1["id"]
            if fighter1
            else ""
        ),

        fighter2_id=(
            fighter2["id"]
            if fighter2
            else ""
        )
    )


@app.route("/analytics")
def analytics():
    connection = connect_database()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM fighters
    """)

    fighter_count = (
        cursor.fetchone()[0]
    )

    cursor.execute("""
        SELECT AVG(
            striking_accuracy
        )

        FROM fighters

        WHERE
            striking_accuracy > 0
    """)

    average_striking_accuracy = (
        cursor.fetchone()[0]
        or 0
    )

    cursor.execute("""
        SELECT AVG(
            takedown_accuracy
        )

        FROM fighters

        WHERE
            takedown_accuracy > 0
    """)

    average_takedown_accuracy = (
        cursor.fetchone()[0]
        or 0
    )

    cursor.execute("""
        SELECT AVG(
            significant_strikes_per_minute
        )

        FROM fighters

        WHERE
            significant_strikes_per_minute > 0
    """)

    average_slpm = (
        cursor.fetchone()[0]
        or 0
    )

    cursor.execute("""
        SELECT AVG(
            takedown_defense
        )

        FROM fighters

        WHERE
            takedown_defense > 0
    """)

    average_td_defense = (
        cursor.fetchone()[0]
        or 0
    )

    cursor.execute("""
        SELECT
            weight_class,
            COUNT(*) AS total

        FROM fighters

        GROUP BY
            weight_class

        ORDER BY
            total DESC
    """)

    divisions = (
        cursor.fetchall()
    )

    cursor.execute("""
        SELECT
            name,
            significant_strikes_per_minute

        FROM fighters

        WHERE
            significant_strikes_per_minute
            > 0

        ORDER BY
            significant_strikes_per_minute
            DESC

        LIMIT 10
    """)

    top_strikers = (
        cursor.fetchall()
    )

    cursor.execute("""
        SELECT
            name,
            takedown_average

        FROM fighters

        WHERE
            takedown_average
            > 0

        ORDER BY
            takedown_average
            DESC

        LIMIT 10
    """)

    top_grapplers = (
        cursor.fetchall()
    )

    connection.close()

    return render_template(
        "analytics.html",

        fighter_count=(
            fighter_count
        ),

        average_striking_accuracy=(
            round(
                average_striking_accuracy,
                1
            )
        ),

        average_takedown_accuracy=(
            round(
                average_takedown_accuracy,
                1
            )
        ),

        average_slpm=(
            round(
                average_slpm,
                2
            )
        ),

        average_td_defense=(
            round(
                average_td_defense,
                1
            )
        ),

        divisions=divisions,

        top_strikers=(
            top_strikers
        ),

        top_grapplers=(
            top_grapplers
        )
    )


# =========================================================
# RUN
# =========================================================


# Historical odds are isolated from the original fighter and fight tables.
def historical_data():
    if 'historical_odds' not in g:
        g.historical_odds = betting_analytics.load_bouts(DATABASE)
    return g.historical_odds


@app.template_filter('odds')
def format_odds(value):
    return f'{value:+g}' if value is not None else 'Unavailable'


@app.template_filter('rate')
def format_rate(value):
    return f'{value:.1f}%' if value is not None else 'N/A'


@app.context_processor
def historical_helpers():
    return dict(
        fighter_betting=lambda fighter: betting_analytics.fighter_context(historical_data()[0], fighter),
        metric_notes=betting_analytics.metric_notes,
    )


@app.route('/betting')
def betting():
    rows, metadata = historical_data()
    divisions = sorted({r['division'] for r in rows})
    years = sorted({r['fight_date'][:4] for r in rows}, reverse=True)
    division = request.args.get('division', '')
    year = request.args.get('year', '')
    filtered = [r for r in rows if (not division or r['division']==division) and (not year or r['fight_date'][:4]==year)]
    coverage = (min(r['fight_date'] for r in rows), max(r['fight_date'] for r in rows)) if rows else None
    return render_template('betting.html', data=betting_analytics.dashboard(filtered),
        metadata=metadata, coverage=coverage, divisions=divisions, years=years,
        division=division, year=year, source_page=betting_analytics.SOURCE_PAGE)


if __name__ == "__main__":
    app.run(
        debug=True
    )