import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from btree import BTree
from db import DB
from sql import SQLError


class TBTree(unittest.TestCase):
    def test_random_vs_dict(self):
        for t in (2, 3, 8):
            b, m = BTree(t), {}
            for _ in range(4000):
                k = random.randint(0, 300)
                if random.random() < 0.6:
                    self.assertEqual(b.put(k, k * 2), k not in m)
                    m[k] = k * 2
                else:
                    self.assertEqual(b.delete(k), k in m)
                    m.pop(k, None)
                self.assertEqual(len(b), len(m))
            self.assertEqual(list(b.scan()), sorted(m.items()))
            for k in range(-5, 306):
                self.assertEqual(b.get(k), m.get(k))

    def test_range(self):
        b = BTree(2)
        for i in range(100):
            b.put(i, i)
        self.assertEqual([k for k, _ in b.scan(10, 20)], list(range(10, 21)))
        self.assertEqual([k for k, _ in b.scan(95)], list(range(95, 100)))
        self.assertEqual([k for k, _ in b.scan(None, 3)], [0, 1, 2, 3])


class TSQL(unittest.TestCase):
    def setUp(s):
        s.d = DB()
        s.d.run("CREATE TABLE u (id INT PRIMARY KEY, name TEXT, age INT)")
        s.d.run("INSERT INTO u VALUES (3,'c',30),(1,'a',10),(2,'b',20),(4,'d',NULL)")

    def q(s, sql):
        return s.d.run(sql)[-1]

    def test_select(s):
        s.assertEqual(s.q("SELECT * FROM u")['rows'][0], [1, 'a', 10])
        s.assertEqual(s.q("SELECT name FROM u WHERE age > 15 ORDER BY age DESC")['rows'], [['c'], ['b']])
        s.assertEqual(s.q("SELECT COUNT(*) FROM u WHERE id <> 2")['rows'], [[3]])
        s.assertEqual(len(s.q("SELECT * FROM u LIMIT 2")['rows']), 2)
        s.assertEqual(s.q("SELECT * FROM u WHERE NOT (id = 1 OR id = 2)")['rows'][0][0], 3)

    def test_plan(s):
        s.assertIn('point lookup', s.q("SELECT * FROM u WHERE id = 2")['plan'])
        s.assertIn('range scan', s.q("SELECT * FROM u WHERE id > 1 AND id < 4")['plan'])
        s.assertEqual(s.q("SELECT * FROM u WHERE name = 'a'")['plan'], 'full table scan')
        s.assertEqual(s.q("SELECT * FROM u WHERE id > 1 AND id < 4")['rows'], [[2, 'b', 20], [3, 'c', 30]])

    def test_dml(s):
        s.q("UPDATE u SET age = 99 WHERE id = 1")
        s.assertEqual(s.q("SELECT age FROM u WHERE id = 1")['rows'], [[99]])
        s.q("DELETE FROM u WHERE id >= 3")
        s.assertEqual(s.q("SELECT COUNT(*) FROM u")['rows'], [[2]])

    def test_errors(s):
        for bad in ["INSERT INTO u VALUES (1,'x',1)", "INSERT INTO u VALUES (9,'x')", "INSERT INTO u VALUES ('z','x',1)",
                    "SELECT * FROM nope", "SELECT zz FROM u", "UPDATE u SET id = 5", "CREATE TABLE u (a INT)", "SELEKT 1",
                    "INSERT INTO u VALUES (7,'x',1),(7,'y',2)"]:
            with s.assertRaises(SQLError, msg=bad):
                s.d.run(bad)
        s.assertEqual(s.q("SELECT COUNT(*) FROM u")['rows'], [[4]])

    def test_no_pk_and_strings(s):
        s.d.run("CREATE TABLE n (v TEXT)")
        s.d.run("INSERT INTO n VALUES ('it''s'),('b'),('b')")
        s.assertEqual(s.q("SELECT * FROM n")['rows'], [["it's"], ['b'], ['b']])


class TDisk(unittest.TestCase):
    def test_persist_and_wal(self):
        p = os.path.join(tempfile.mkdtemp(), 'db.json')
        d = DB(p)
        d.run("CREATE TABLE t (id INT PRIMARY KEY, v TEXT)")
        d.run("INSERT INTO t VALUES (1,'a'),(2,'b')")
        d.run("UPDATE t SET v = 'z' WHERE id = 2")
        d.run("DELETE FROM t WHERE id = 1")
        d.wal.close()
        d2 = DB(p)
        self.assertEqual(d2.run("SELECT * FROM t")[0]['rows'], [[2, 'z']])
        d2.close()
        d3 = DB(p)
        self.assertEqual(d3.run("SELECT * FROM t")[0]['rows'], [[2, 'z']])
        d3.run("INSERT INTO t VALUES (5,'e')")
        d3.close()
        self.assertEqual(len(DB(p).run("SELECT * FROM t")[0]['rows']), 2)


if __name__ == '__main__':
    unittest.main()
