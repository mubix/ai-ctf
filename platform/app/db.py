import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("CTF_DB_PATH", "/data/ctf.db"))
INIT_SQL = Path(__file__).resolve().parents[1] / "data" / "init.sql"
LEARNING_SQL = Path(__file__).resolve().parent / "learning.sql"


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript(INIT_SQL.read_text())
        conn.executescript(LEARNING_SQL.read_text())
        columns = {row[1] for row in conn.execute("PRAGMA table_info(learning_runs)")}
        if "profile" not in columns:
            conn.execute("ALTER TABLE learning_runs ADD COLUMN profile TEXT NOT NULL DEFAULT 'legacy'")
        conn.commit()


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
