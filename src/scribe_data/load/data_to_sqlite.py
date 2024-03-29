"""
Converts all or desired JSON data generated by update_data into SQLite databases.

Parameters
----------
    languages : list of strings (default=None)
        A subset of Scribe's languages that the user wants to update.

Example
-------
    python data_to_sqlite.py '["French", "German"]'
"""

import ast
import json
import os
import sqlite3
import sys

from tqdm.auto import tqdm

from scribe_data.utils import get_language_iso

PATH_TO_ET_FILES = "../extract_transform/"

with open("update_files/total_data.json", encoding="utf-8") as f:
    current_data = json.load(f)

current_languages = list(current_data.keys())
word_types = [
    "nouns",
    "verbs",
    "prepositions",
    "translations",
    "autosuggestions",
    "emoji_keywords",
]

# Note: Check whether an argument has been passed to only update a subset of the data.
languages = None
if len(sys.argv) == 2:
    arg = sys.argv[1]

    try:
        arg = ast.literal_eval(arg)
    except ValueError as invalid_arg:
        raise ValueError(
            f"""The argument type of '{arg}' passed to data_to_sqlite.py is invalid.
            Only lists are allowed, and can be passed via:
            python data_to_sqlite.py '[comma_separated_args_in_quotes]'
            """
        ) from invalid_arg

    if not isinstance(arg, list):
        raise ValueError(
            f"""The argument type of '{arg}' passed to data_to_sqlite.py is invalid.
            Only lists are allowed, and can be passed via:
            python data_to_sqlite.py '[comma_separated_args_in_quotes]'
            """
        )

    if set(arg).issubset(current_languages):
        languages = arg
    else:
        raise ValueError(
            f"""An invalid argument '{arg}' was specified.
                Please choose a language from those found as keys in total_data.json.
                """
        )

# Note: Derive tables to be made, prepare paths for process and create databases.
languages_update = current_languages if languages is None else languages

language_word_type_dict = {
    lang: [
        f.split(".json")[0]
        for f in os.listdir(f"{PATH_TO_ET_FILES}{lang}/formatted_data")
        if f.split(".json")[0] in word_types
    ]
    for lang in languages_update
}

print(
    f"Creating SQLite databases for the following languages: {', '.join(languages_update)}"
)
for lang in tqdm(
    language_word_type_dict,
    desc="Databases created",
    unit="dbs",
):
    if language_word_type_dict[lang] != []:
        maybe_over = ""  # output string formatting variable (see below)
        if os.path.exists(
            f"databases/{get_language_iso(lang).upper()}LanguageData.sqlite"
        ):
            os.remove(f"databases/{get_language_iso(lang).upper()}LanguageData.sqlite")
            maybe_over = "over"

        connection = sqlite3.connect(
            f"databases/{get_language_iso(lang).upper()}LanguageData.sqlite"
        )
        cursor = connection.cursor()

        def create_table(word_type, cols):
            """
            Creates a table in the language database given a word type for its title and column names.

            Parameters
            ----------
                word_type : str
                    The name of the table to be created

                cols : list of strings
                    The names of columns for the new table
            """
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {word_type} ({' Text, '.join(cols)} Text, UNIQUE({cols[0]}))"
            )

        def table_insert(word_type, keys):
            """
            Inserts a row into a language database table.

            Parameters
            ----------
                word_type : str
                    The name of the table to be inserted into

                keys : list of strings
                    The values to be inserted into the table row
            """
            insert_question_marks = ", ".join(["?"] * len(keys))
            cursor.execute(
                f"INSERT OR IGNORE INTO {word_type} values({insert_question_marks})",
                keys,
            )

        print(f"Database for {lang} {maybe_over}written and connection made.")
        for wt in language_word_type_dict[lang]:
            print(f"Creating {lang} {wt} table...")
            json_data = json.load(
                open(f"{PATH_TO_ET_FILES}{lang}/formatted_data/{wt}.json")
            )

            if wt == "nouns":
                cols = ["noun, plural, form"]
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row, json_data[row]["plural"], json_data[row]["form"]]
                    table_insert(word_type=wt, keys=keys)

                if "Scribe" not in json_data and lang != "Russian":
                    table_insert(word_type=wt, keys=["Scribe", "Scribes", ""])
                # elif "Писец" not in json_data and lang == "Russian":
                #     table_insert(word_type=wt, keys=["Писец", "Писцы", ""])

                connection.commit()

            elif wt == "verbs":
                cols = ["verb"]
                cols += json_data[list(json_data.keys())[0]].keys()
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row]
                    keys += [json_data[row][col_name] for col_name in cols[1:]]
                    table_insert(word_type=wt, keys=keys)

                connection.commit()

            elif wt == "prepositions":
                cols = ["preposition, form"]
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row, json_data[row]]
                    table_insert(word_type=wt, keys=keys)

                connection.commit()

            elif wt == "translations":
                cols = ["word, translation"]
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row, json_data[row]]
                    table_insert(word_type=wt, keys=keys)

                connection.commit()

            elif wt == "autosuggestions":
                cols = ["word", "suggestion_0", "suggestion_1", "suggestion_2"]
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row]
                    keys += [json_data[row][i] for i in range(len(json_data[row]))]
                    keys += [""] * (len(cols) - len(keys))
                    table_insert(word_type=wt, keys=keys)

                connection.commit()

            elif wt == "emoji_keywords":
                cols = ["word", "emoji_0", "emoji_1", "emoji_2"]
                create_table(word_type=wt, cols=cols)
                for row in json_data:
                    keys = [row]
                    keys += [
                        json_data[row][i]["emoji"] for i in range(len(json_data[row]))
                    ]
                    keys += [""] * (len(cols) - len(keys))
                    table_insert(word_type=wt, keys=keys)

                connection.commit()

        wt = "autocomplete_lexicon"
        print(f"Creating {lang} {wt} table...")
        cols = ["word"]
        create_table(word_type=wt, cols=cols)

        cursor.execute(
            """
            INSERT INTO autocomplete_lexicon (word)

            WITH full_lexicon AS (
                SELECT
                noun AS word
                FROM
                nouns
                WHERE
                LENGTH(noun) > 2

                UNION

                SELECT
                preposition AS word
                FROM
                prepositions
                WHERE
                LENGTH(preposition) > 2

                UNION

                SELECT DISTINCT
                -- For autosuggestion keys we want lower case versions.
                -- The SELECT DISTINCT cases later will make sure that nouns are appropriately selected.
                LOWER(word) AS word
                FROM
                autosuggestions
                WHERE
                LENGTH(word) > 2

                UNION

                SELECT
                word AS word
                FROM
                emoji_keywords
            )

            SELECT DISTINCT
                -- Select an upper case noun if it's available.
                CASE
                    WHEN
                        UPPER(SUBSTR(lex.word, 1, 1)) || SUBSTR(lex.word, 2) = nouns_cap.noun
                    THEN
                        nouns_cap.noun

                    WHEN
                        UPPER(lex.word) = nouns_upper.noun
                    THEN
                        nouns_upper.noun

                    ELSE
                        lex.word
                END

            FROM
                full_lexicon AS lex

            LEFT JOIN
                nouns AS nouns_cap

            ON
                UPPER(SUBSTR(lex.word, 1, 1)) || SUBSTR(lex.word, 2) = nouns_cap.noun

            LEFT JOIN
                nouns AS nouns_upper

            ON
                UPPER(lex.word) = nouns_upper.noun

            WHERE
                LENGTH(lex.word) > 1
                AND lex.word NOT LIKE '%-%'
                AND lex.word NOT LIKE '%/%'
                AND lex.word NOT LIKE '%(%'
                AND lex.word NOT LIKE '%)%'
                AND lex.word NOT LIKE '%"%'
                AND lex.word NOT LIKE '%“%'
                AND lex.word NOT LIKE '%„%'
                AND lex.word NOT LIKE '%”%'
                AND lex.word NOT LIKE "%'%"
            """
        )

        connection.commit()

        print(f"{lang} database created.")

    else:
        print(f"Skipping {lang} database creation as no JSON data files were found.")
