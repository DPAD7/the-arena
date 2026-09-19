"""Cut the two registers out of qbspy.db into a database small enough to commit.

   data/qbspy.db is six gigabytes and git ignores it, so a machine that is not
   this Mac has no way to get it. That would be the end of running the sweep
   anywhere else — except that the scheduled scripts do not want the play
   record at all. fill_week.py, networks.py, score_watch.py and x_clips.py open
   the file for exactly two tables:

       club_name     every way a board writes a club, pinned to one abbr
       person_name   every way a source writes a man, pinned to one ESPN id

   Neither is large. Both together come out around 228 KB, which is a file the
   repository can carry, so a runner with no Mac behind it can look a name up
   the same way this one does.

   The copy is written to data/register.db. The workflow in
   .github/workflows/sweep.yml copies it to data/qbspy.db at the start of each
   run, because every script names that path and none of them should have to
   learn a second one. That working copy is thrown away when the run ends.

   Rerun this whenever build/people.py or build/register.py over in QB Spy adds
   spellings — a name missing from the register is a card that silently never
   appears (Jose, Sep 19, 2026).

   Usage:  python3 build/make_register.py
"""
import os
import sqlite3

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIG = os.path.join(D, "data", "qbspy.db")
SMALL = os.path.join(D, "data", "register.db")

# Only these. Anything else and the file stops being small, and a big file in
# the repository is a thing nobody can undo later.
TABLES = ("club_name", "person_name")


def main():
    if not os.path.exists(BIG):
        raise SystemExit("no %s here — this runs on the Mac that holds it" % BIG)
    if os.path.exists(SMALL):
        os.remove(SMALL)

    # Read-only: this script has no business writing to the play record, and
    # opening it read-only means a build running alongside cannot be disturbed.
    db = sqlite3.connect("file:%s?mode=ro" % BIG, uri=True)
    db.execute("ATTACH DATABASE ? AS small", (SMALL,))

    for t in TABLES:
        # Take the table's own CREATE statement rather than writing one here:
        # a column added upstream should arrive with the table, not go missing
        # because this script still remembers the old shape.
        for kind, sql in db.execute(
                "SELECT type, sql FROM main.sqlite_master "
                "WHERE tbl_name = ? AND sql IS NOT NULL "
                "ORDER BY type = 'index'", (t,)):
            db.execute(sql.replace("CREATE TABLE ", "CREATE TABLE small.", 1)
                          .replace("CREATE INDEX ", "CREATE INDEX small.", 1)
                          .replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX small.", 1))
        db.execute("INSERT INTO small.%s SELECT * FROM main.%s" % (t, t))
        db.commit()
        n = db.execute("SELECT count(*) FROM small.%s" % t).fetchone()[0]
        print("%-12s %6d rows" % (t, n))

    db.execute("DETACH DATABASE small")
    db.close()

    # Squeeze out the free pages the inserts left behind, so the committed file
    # is the size of what is in it.
    out = sqlite3.connect(SMALL)
    out.execute("VACUUM")
    out.close()

    size = os.path.getsize(SMALL)
    print("%s  %.0f KB" % (SMALL, size / 1024.0))


if __name__ == "__main__":
    main()
