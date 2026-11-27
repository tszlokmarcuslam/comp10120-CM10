import sqlite3
import pandas as pd

RAW_DATA_PATH = "imdb_data.csv"
DB_PATH = "movies.db"

def extract_imdb_id(url: str) -> str:
    # If the URL is not a string, return ""
    if not isinstance(url, str):
        return ""

    # Split the URL after "tt" then collect the digits after it
    for i in url.split("tt")[1:]:
        digits = ""
        for character in i:
            if character.isdigit():
                digits += character
            else:
                break

    # If the collected digits are not empty then return the ID
        if digits:
            return "tt" + digits

    return ""
    


def clean_year(val) -> int:
    digits = ""
    # Check for a 4 digits year in the string and return it as an integer
    for character in str(val):
        if character.isdigit():
            digits += character
            if len(digits) == 4:
                return int(digits)
        else:
            digits = ""

    return 0


def load_and_clean_data(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, na_values=["\\N", "N/A", ""], low_memory=False)

    # Make headings lowercase and strip whitespace so it will be easier to compare it with other strings
    columns = []
    for col in df.columns:
        columns.append(col.strip().lower())
    df.columns = columns

    # Iterate through each row and drop those certificate marked as adult 
    valid_certificate = []
    for i, row in df.iterrows():
        if not str(row["certificate"]).strip().lower() == "adult":
            valid_certificate.append(i)

    df = df.loc[valid_certificate]


    # Convert all values in these columns to string and create the columns in the database
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["poster_url"] = df["image"].fillna("").astype(str).str.strip()
    df["genres"] = df["genre"].fillna("").astype(str).str.strip()
    df["plot"] = df["synopsis"].fillna("No plot summary available.").astype(str).str.strip()
    df["director"] = df["director"].fillna("Unknown").astype(str).str.strip()
    df["imdb_rating"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0.0)
    df["release_year"] = df["year"].apply(clean_year)
    df["imdb_id"] = df["title_url"].apply(extract_imdb_id)
    backup_posters = df["listeritemimage_url"].fillna("")
    backup_posters = backup_posters.astype(str).str.strip()

    # Fill missing poster url with backup poster url
    blank_posters = df["poster_url"] == ""
    df.loc[blank_posters, "poster_url"] = backup_posters[blank_posters]

    # Remove rows without a title
    valid_titles = (df["title"] != "") & (df["title"].str.lower() != "nan")
    df = df[valid_titles]

    # Remove rows without a genre or genre marked as adult 
    valid_genres = (df["genres"] != "") & (df["genres"].str.lower() != "nan") & (df["genres"].str.lower() != "adult")
    df = df[valid_genres]

    # If there are duplicates, keep the one with highest rating
    df = df.sort_values(by="imdb_rating", ascending=False)
    df = df.drop_duplicates(subset=["title", "release_year"], keep="first")

    # Form the synopsis
    df["synopsis"] = (df["title"] + " | " + df["genres"] + " | Director: " + df["director"] + " | " + df["plot"])

    final_cols = ["imdb_id", "title", "genres", "director", "plot", "imdb_rating", "release_year", "poster_url", "synopsis"]
    return df[final_cols].reset_index(drop=True)


def create_database(df: pd.DataFrame, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS movies;")

    cursor.execute("""CREATE TABLE movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        imdb_id TEXT,
        title TEXT NOT NULL,
        genres TEXT NOT NULL,
        director TEXT,
        plot TEXT,
        imdb_rating REAL,
        release_year INTEGER,
        poster_url TEXT,
        synopsis TEXT) """)

    df.to_sql("movies", conn, if_exists="append", index=False)

    # Index title for fast lookup queries from Flask
    cursor.execute("CREATE INDEX idx_movie_title ON movies (title);")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    cleaned_df = load_and_clean_data(RAW_DATA_PATH)
    create_database(cleaned_df, DB_PATH)