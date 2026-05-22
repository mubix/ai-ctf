import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("/data/ctf.db")
INIT_SQL = Path("/app/data/init.sql")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(INIT_SQL.read_text())
        conn.commit()


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
