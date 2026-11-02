#!/bin/bash
# carry-params.sh (2026-10-30, mine): every source's carry trigger hands its return to mother as bound parameters instead of a text built by
# concatenation (the same insert; the statement text is now one and the same for every return, so mother prepares it once). Run on hp over a
# folder of source files: bash carry-params.sh sources-egg; bash carry-params.sh sources
cd ~/nk/$1 || exit 1
for f in *.db; do
  old=$(sqlite3 "$f" "SELECT sql FROM sqlite_master WHERE name = 'carry'")
  case "$old" in *"VALUES (?, ?, ?, ?, ?)"*) echo "$f: already by parameters"; continue;; esac
  sqlite3 "$f" "DROP TRIGGER carry; CREATE TRIGGER carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text) VALUES (?, ?, ?, ?, ?)', NEW.run, NEW.cell, (SELECT gate FROM me), NEW.about, NEW.text);
  DELETE FROM outbox WHERE id = NEW.id;
END;" && echo "$f: carry by parameters"
done
