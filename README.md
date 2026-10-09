# minidb

A small relational database engine written from scratch in Python (standard library only).

- **B-tree** storage engine (insert, update, delete, ordered range scans), no external libraries
- **SQL parser**: hand-written tokenizer + recursive-descent parser
- **Query planner**: uses the B-tree for `WHERE` on the primary key, full scan otherwise; `EXPLAIN` shows which
- **Durability**: write-ahead log (fsync on every write) + atomic snapshot checkpoints, crash recovery by log replay
- **Web UI** and **CLI**, plus tests and a benchmark

## Run

    python cli.py demo.sql              # run a script file
    python cli.py --db my.json          # interactive shell, saved to disk
    python server.py --db data.json     # web UI at http://127.0.0.1:8000
    python tests/test_all.py            # tests
    python bench.py                     # B-tree lookup vs full scan

## SQL supported

    CREATE TABLE t (id INT PRIMARY KEY, name TEXT, score REAL)
    INSERT INTO t VALUES (1,'a',2.5),(2,'b',3)      INSERT INTO t (id,name) VALUES (3,'c')
    SELECT * | col,col | COUNT(*) FROM t [WHERE ...] [ORDER BY col [DESC]] [LIMIT n]
    UPDATE t SET col = value [WHERE ...]            DELETE FROM t [WHERE ...]
    DROP TABLE t      SHOW TABLES      EXPLAIN SELECT ...
    WHERE: = != <> < <= > >= with AND, OR, NOT and parentheses

## Architecture

    sql.py     text -> tokens -> AST
    db.py      AST -> plan -> execution, WAL + snapshots
    btree.py   B-tree (min degree t): split on the way down for insert, merge/borrow for delete
    server.py  JSON API (POST /api/query) + static page
    web/       query UI

## Design notes and limits

- Rows live in memory; the snapshot is rewritten at each checkpoint (every 500 writes and on clean shutdown). A real engine would page the tree to disk.
- The WAL stores the SQL text of each successful write; replaying it after a crash rebuilds the exact state.
- Only the primary key is indexed. Secondary indexes and transactions are the natural next steps.
- No joins, no GROUP BY.
