import time

from db import DB

N = 50000
d = DB()
d.run('CREATE TABLE t (id INT PRIMARY KEY, name TEXT)')
t0 = time.perf_counter()
d.run('INSERT INTO t VALUES ' + ','.join(f"({i},'n{i}')" for i in range(N)))
print(f'insert {N} rows: {time.perf_counter() - t0:.2f}s, btree height {d.tb["t"].t.height()}')


def avg(q, k):
    t0 = time.perf_counter()
    for i in range(k):
        d.run(q.format(i * 997 % N))
    return (time.perf_counter() - t0) / k * 1000


a = avg("SELECT * FROM t WHERE id = {}", 500)
b = avg("SELECT * FROM t WHERE name = 'n{}'", 10)
print(f'B-tree lookup: {a:.3f} ms/query')
print(f'full scan:     {b:.3f} ms/query')
print(f'speedup:       {b / a:.0f}x')
