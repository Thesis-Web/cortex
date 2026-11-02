#!/bin/bash
# carry-src.sh (2026-10-30, mine): every source's return carries the row it came from (src), so the brain keeps a pointer to the definition's
# source row and not a copy of its text. The outbox gets a src column; the work trigger of a dictionary source writes the corpus row id into
# it; the carry trigger hands it to mother with the return. The guesser's work trigger is left as it is (its returns carry no src).
# usage: bash carry-src.sh <folder of source files>
cd ~/nk/$1 || exit 1
for f in *.db; do
  sqlite3 "$f" "SELECT 1 FROM pragma_table_info('outbox') WHERE name = 'src'" | grep -q 1 || sqlite3 "$f" "ALTER TABLE outbox ADD COLUMN src INTEGER"
  if [ "$f" != guess.db ]; then
    sqlite3 "$f" "DROP TRIGGER IF EXISTS work; CREATE TRIGGER work AFTER INSERT ON inbox BEGIN
  INSERT INTO outbox (run, cell, about, text, src) SELECT NEW.run, NEW.cell, NEW.about, text, id FROM corpus WHERE word = NEW.word ORDER BY id;
  DELETE FROM inbox WHERE id = NEW.id;
END;"
  fi
  sqlite3 "$f" "DROP TRIGGER IF EXISTS carry; CREATE TRIGGER carry AFTER INSERT ON outbox BEGIN
  SELECT mother('INSERT INTO main.secondary (run, cell, gate, about, text, src) VALUES (?, ?, ?, ?, ?, ?)', NEW.run, NEW.cell, (SELECT gate FROM me), NEW.about, NEW.text, NEW.src);
  DELETE FROM outbox WHERE id = NEW.id;
END;" && echo "$f: returns carry their source row"
done
