import json
import operator as o
import os
import time

from btree import BTree
from sql import SQLError, parse

OP = {'=': o.eq, '!=': o.ne, '<': o.lt, '<=': o.le, '>': o.gt, '>=': o.ge}
MUT = {'create', 'insert', 'update', 'delete', 'drop'}
WI = {'select': 3, 'update': 3, 'delete': 2}


class Table:
    def __init__(s, n, cols, pk):
        s.n, s.cols, s.pk = n, cols, pk
        s.names = [c for c, _ in cols]
        s.t = BTree()
        s.nid = 1

    def col(s, c):
        if c not in s.names:
            raise SQLError(f'no such column: {c}')
        return s.names.index(c)

    def cast(s, i, v):
        ty = s.cols[i][1]
        if v is None:
            if i == s.pk:
                raise SQLError('primary key cannot be NULL')
            return None
        if ty == 'INT' and type(v) is float and v.is_integer():
            v = int(v)
        ok = (ty == 'INT' and type(v) is int) or (ty == 'REAL' and type(v) in (int, float)) or (ty == 'TEXT' and type(v) is str)
        if not ok:
            raise SQLError(f'bad value {v!r} for column {s.names[i]} ({ty})')
        return float(v) if ty == 'REAL' else v

    def add(s, r):
        if s.pk is None:
            k = s.nid
            s.nid += 1
        else:
            k = r[s.pk]
        s.t.put(k, r)


def conj(w):
    return conj(w[1]) + conj(w[2]) if w[0] == 'and' else [w]


def cmps(w):
    if w[0] in ('and', 'or'):
        return cmps(w[1]) + cmps(w[2])
    return cmps(w[1]) if w[0] == 'not' else [w]


def ev(w, r):
    k = w[0]
    if k == 'and':
        return ev(w[1], r) and ev(w[2], r)
    if k == 'or':
        return ev(w[1], r) or ev(w[2], r)
    if k == 'not':
        return not ev(w[1], r)
    a, b = r[w[1]], w[3]
    if a is None or b is None:
        return False
    try:
        return OP[w[2]](a, b)
    except TypeError:
        return False


class DB:
    def __init__(s, path=None, every=500):
        s.tb = {}
        s.path = path
        s.every = every
        s.nw = 0
        s.wal = None
        if path:
            s._load()

    def _load(s):
        if os.path.exists(s.path):
            with open(s.path) as f:
                d = json.load(f)
            for n, m in d.items():
                t = Table(n, [tuple(c) for c in m['cols']], m['pk'])
                for r in m['rows']:
                    t.add(r)
                s.tb[n] = t
        w = s.path + '.wal'
        if os.path.exists(w):
            with open(w) as f:
                s.run(f.read(), log=False)
        s.wal = open(w, 'a')

    def checkpoint(s):
        if not s.path:
            return
        d = {n: {'cols': t.cols, 'pk': t.pk, 'rows': [r for _, r in t.t.scan()]} for n, t in s.tb.items()}
        tmp = s.path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(d, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, s.path)
        s.wal.close()
        s.wal = open(s.path + '.wal', 'w')
        s.nw = 0

    def close(s):
        if s.path:
            s.checkpoint()
            s.wal.close()

    def _log(s, txt):
        s.wal.write(txt + ';\n')
        s.wal.flush()
        os.fsync(s.wal.fileno())
        s.nw += 1
        if s.nw >= s.every:
            s.checkpoint()

    def run(s, sql, log=True):
        out = []
        for st, txt in parse(sql):
            t0 = time.perf_counter()
            r = getattr(s, 'x_' + st[0])(st)
            if log and s.wal and st[0] in MUT:
                s._log(txt)
            r['ms'] = round((time.perf_counter() - t0) * 1000, 3)
            out.append(r)
        return out

    def get(s, n):
        if n not in s.tb:
            raise SQLError(f'no such table: {n}')
        return s.tb[n]

    def bounds(s, t, w):
        if t.pk is None or w is None:
            return None, None, False
        pc, lo, hi, used = t.names[t.pk], None, None, False
        for c in conj(w):
            if c[0] == 'cmp' and c[1] == pc and c[2] in ('=', '<', '<=', '>', '>=') and c[3] is not None:
                try:
                    v = t.cast(t.pk, c[3])
                except SQLError:
                    continue
                used = True
                if c[2] in ('=', '>', '>=') and (lo is None or v > lo):
                    lo = v
                if c[2] in ('=', '<', '<=') and (hi is None or v < hi):
                    hi = v
        return lo, hi, used

    def match(s, t, w):
        if w:
            for c in cmps(w):
                t.col(c[1])
        lo, hi, used = s.bounds(t, w)
        pc = t.names[t.pk] if t.pk is not None else ''
        if used:
            plan = f'B-tree point lookup on {pc}' if lo is not None and lo == hi else f'B-tree range scan on {pc}'
        else:
            plan = 'full table scan'
        it = t.t.scan(lo, hi) if used else t.t.scan()
        rows = [(k, r) for k, r in it if w is None or ev(w, dict(zip(t.names, r)))]
        return rows, plan

    def x_create(s, st):
        _, n, cols, pk = st
        if n in s.tb:
            raise SQLError(f'table {n} already exists')
        s.tb[n] = Table(n, cols, pk)
        return {'msg': f'table {n} created'}

    def x_drop(s, st):
        s.get(st[1])
        del s.tb[st[1]]
        return {'msg': f'table {st[1]} dropped'}

    def x_show(s, st):
        rows = [[n, ', '.join(f'{c} {y}' for c, y in t.cols), len(t.t), t.t.height()] for n, t in s.tb.items()]
        return {'cols': ['table', 'columns', 'rows', 'btree_height'], 'rows': rows, 'msg': f'{len(rows)} table(s)'}

    def x_insert(s, st):
        _, n, cl, rows = st
        t = s.get(n)
        idx = [t.col(c) for c in cl] if cl else list(range(len(t.names)))
        rs = []
        for vals in rows:
            if len(vals) != len(idx):
                raise SQLError(f'expected {len(idx)} values, got {len(vals)}')
            r = [None] * len(t.names)
            for i, v in zip(idx, vals):
                r[i] = t.cast(i, v)
            rs.append(r)
        if t.pk is not None:
            ks = [r[t.pk] for r in rs]
            if None in ks:
                raise SQLError('primary key cannot be NULL')
            if len(set(ks)) < len(ks) or any(t.t.get(k) is not None for k in ks):
                raise SQLError('duplicate primary key')
        for r in rs:
            t.add(r)
        return {'msg': f'{len(rs)} row(s) inserted'}

    def x_select(s, st):
        _, n, cols, w, ob, lim = st
        t = s.get(n)
        rows, plan = s.match(t, w)
        if cols == 'count':
            return {'cols': ['count'], 'rows': [[len(rows)]], 'plan': plan, 'msg': '1 row(s)'}
        rs = [r for _, r in rows]
        if ob:
            i = t.col(ob[0])
            rs.sort(key=lambda r: (r[i] is None, 0 if r[i] is None else r[i]), reverse=ob[1])
        if lim is not None:
            rs = rs[:lim]
        if cols == '*':
            names = t.names
        else:
            ix = [t.col(c) for c in cols]
            names = cols
            rs = [[r[i] for i in ix] for r in rs]
        return {'cols': names, 'rows': rs, 'plan': plan, 'msg': f'{len(rs)} row(s)'}

    def x_update(s, st):
        _, n, sets, w = st
        t = s.get(n)
        ch = []
        for c, v in sets:
            i = t.col(c)
            if i == t.pk:
                raise SQLError('cannot update the primary key')
            ch.append((i, t.cast(i, v)))
        rows, plan = s.match(t, w)
        for _, r in rows:
            for i, v in ch:
                r[i] = v
        return {'msg': f'{len(rows)} row(s) updated', 'plan': plan}

    def x_delete(s, st):
        _, n, w = st
        t = s.get(n)
        rows, plan = s.match(t, w)
        for k, _ in rows:
            t.t.delete(k)
        return {'msg': f'{len(rows)} row(s) deleted', 'plan': plan}

    def x_explain(s, st):
        q = st[1]
        _, plan = s.match(s.get(q[1]), q[WI[q[0]]])
        return {'cols': ['plan'], 'rows': [[plan]], 'msg': 'plan only, nothing executed'}
