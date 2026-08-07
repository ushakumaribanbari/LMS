import sqlite3

conn = sqlite3.connect("lms.db")

with open("lms.sql", "w", encoding="utf-8") as f:
    for line in conn.iterdump():
        f.write("%s\n" % line)

conn.close()

print("✅ lms.sql created successfully!")