"""The one way in and out of the database.

   Every script had been opening its own connection and reading rows by
   position — `line[4]`, `row[2]` — which is how a column added in the middle
   of a table quietly broke an insert, and how a query could return the wrong
   season without anything looking wrong. This module owns the connection and
   hands back rows you address by name.

   Use:
       from store import open_db, rows, one, put

       db = open_db()
       for snap in rows(db, "SELECT * FROM snap WHERE subject=1"):
           print(snap["quarter"], snap["gained"])
"""

import os
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "qbspy.db")
SCHEMA = os.path.join(HERE, "schema.sql")


def open_db(path=DB, apply_schema=True):
    """A connection with the settings this project expects.

       Rows come back keyed by column name, foreign keys are enforced, and the
       journal is write-ahead so a long build does not block a read.
    """
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # Write-ahead logging lets a read run while a build writes, but switching
    # to it needs the file to itself. If a build already holds it the mode is
    # already whatever it is, and the connection is still perfectly usable.
    try:
        db.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass

    if apply_schema and os.path.exists(SCHEMA):
        try:
            db.executescript(open(SCHEMA).read())
        except sqlite3.OperationalError:
            pass
    return db


def patiently(work, tries=40, wait=5):
    """Run something that writes, waiting out anyone else holding the file.

       A long build keeps one write transaction open for minutes at a time, and
       SQLite will not let a second writer in while it does. Rather than fail,
       a writer waits its turn — the alternative is every fetcher needing the
       build to be finished first.
    """
    for attempt in range(tries):
        try:
            return work()
        except sqlite3.OperationalError as bad:
            if "locked" not in str(bad) and "busy" not in str(bad):
                raise
            if attempt == tries - 1:
                raise
            if attempt == 0:
                print("   the database is busy; waiting for it")
            time.sleep(wait)


def rows(db, sql, *args):
    """Every row, addressed by column name."""
    return db.execute(sql, args).fetchall()


def one(db, sql, *args):
    """The first row, or None."""
    return db.execute(sql, args).fetchone()


def value(db, sql, *args, default=None):
    """A single number or string out of a query, with a fallback."""
    got = db.execute(sql, args).fetchone()
    if got is None or got[0] is None:
        return default
    return got[0]


def put(db, table, record):
    """Insert or replace, naming every column.

       Naming them means a column added to the table later cannot silently
       shift the values of this call, which is exactly what went wrong when
       `context` grew six columns and its writer still passed sixteen.
    """
    columns = list(record)
    db.execute("INSERT OR REPLACE INTO %s (%s) VALUES (%s)"
               % (table, ", ".join(columns), ", ".join("?" * len(columns))),
               [record[column] for column in columns])


def put_many(db, table, records):
    """The same, for a list. Every record must carry the same columns."""
    records = list(records)
    if not records:
        return 0
    columns = list(records[0])
    db.executemany("INSERT OR REPLACE INTO %s (%s) VALUES (%s)"
                   % (table, ", ".join(columns), ", ".join("?" * len(columns))),
                   [[r[c] for c in columns] for r in records])
    return len(records)


def columns_of(db, table):
    """What a table actually holds right now."""
    return [r["name"] for r in db.execute("PRAGMA table_info(%s)" % table)]


def add_column(db, table, name, kind):
    """Add a column only if it is not already there.

       SQLite has no ADD COLUMN IF NOT EXISTS, so a schema file carrying bare
       ALTERs fails on its second run — which had broken three build steps.
    """
    if name in columns_of(db, table):
        return False
    db.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, kind))
    return True


def counts(db, *tables):
    """How many rows each table holds, for a build to report on itself."""
    return {t: value(db, "SELECT COUNT(*) FROM %s" % t, default=0) for t in tables}
