from bisect import bisect_left


class N:
    __slots__ = ('k', 'v', 'c')

    def __init__(s):
        s.k = []
        s.v = []
        s.c = []


class BTree:
    def __init__(s, t=16):
        s.t = t
        s.r = N()
        s.n = 0

    def __len__(s):
        return s.n

    def height(s):
        h, n = 1, s.r
        while n.c:
            n = n.c[0]
            h += 1
        return h

    def get(s, k, d=None):
        n = s.r
        while 1:
            i = bisect_left(n.k, k)
            if i < len(n.k) and n.k[i] == k:
                return n.v[i]
            if not n.c:
                return d
            n = n.c[i]

    def _split(s, p, i):
        t = s.t
        y = p.c[i]
        z = N()
        mk, mv = y.k[t - 1], y.v[t - 1]
        z.k, z.v = y.k[t:], y.v[t:]
        y.k, y.v = y.k[:t - 1], y.v[:t - 1]
        if y.c:
            z.c, y.c = y.c[t:], y.c[:t]
        p.k.insert(i, mk)
        p.v.insert(i, mv)
        p.c.insert(i + 1, z)

    def put(s, k, v):
        if len(s.r.k) == 2 * s.t - 1:
            r = N()
            r.c = [s.r]
            s._split(r, 0)
            s.r = r
        n = s.r
        while 1:
            i = bisect_left(n.k, k)
            if i < len(n.k) and n.k[i] == k:
                n.v[i] = v
                return False
            if not n.c:
                n.k.insert(i, k)
                n.v.insert(i, v)
                s.n += 1
                return True
            if len(n.c[i].k) == 2 * s.t - 1:
                s._split(n, i)
                if k == n.k[i]:
                    n.v[i] = v
                    return False
                if k > n.k[i]:
                    i += 1
            n = n.c[i]

    def delete(s, k):
        ok = s._del(s.r, k)
        if not s.r.k and s.r.c:
            s.r = s.r.c[0]
        if ok:
            s.n -= 1
        return ok

    def _del(s, n, k):
        t = s.t
        i = bisect_left(n.k, k)
        if i < len(n.k) and n.k[i] == k:
            if not n.c:
                del n.k[i], n.v[i]
                return True
            if len(n.c[i].k) >= t:
                pk, pv = s._edge(n.c[i], -1)
                n.k[i], n.v[i] = pk, pv
                return s._del(n.c[i], pk)
            if len(n.c[i + 1].k) >= t:
                sk, sv = s._edge(n.c[i + 1], 0)
                n.k[i], n.v[i] = sk, sv
                return s._del(n.c[i + 1], sk)
            s._merge(n, i)
            return s._del(n.c[i], k)
        if not n.c:
            return False
        if len(n.c[i].k) < t:
            i = s._fill(n, i)
        return s._del(n.c[i], k)

    def _edge(s, n, side):
        while n.c:
            n = n.c[side]
        return n.k[side], n.v[side]

    def _merge(s, n, i):
        a, b = n.c[i], n.c.pop(i + 1)
        a.k.append(n.k.pop(i))
        a.v.append(n.v.pop(i))
        a.k += b.k
        a.v += b.v
        a.c += b.c

    def _fill(s, n, i):
        t = s.t
        c = n.c[i]
        if i > 0 and len(n.c[i - 1].k) >= t:
            l = n.c[i - 1]
            c.k.insert(0, n.k[i - 1])
            c.v.insert(0, n.v[i - 1])
            n.k[i - 1], n.v[i - 1] = l.k.pop(), l.v.pop()
            if l.c:
                c.c.insert(0, l.c.pop())
            return i
        if i < len(n.c) - 1 and len(n.c[i + 1].k) >= t:
            r = n.c[i + 1]
            c.k.append(n.k[i])
            c.v.append(n.v[i])
            n.k[i], n.v[i] = r.k.pop(0), r.v.pop(0)
            if r.c:
                c.c.append(r.c.pop(0))
            return i
        if i < len(n.c) - 1:
            s._merge(n, i)
            return i
        s._merge(n, i - 1)
        return i - 1

    def scan(s, lo=None, hi=None):
        return s._scan(s.r, lo, hi)

    def _scan(s, n, lo, hi):
        for i in range(len(n.k) + 1):
            k = n.k[i] if i < len(n.k) else None
            if n.c and (k is None or lo is None or lo < k):
                yield from s._scan(n.c[i], lo, hi)
            if k is None:
                return
            if hi is not None and k > hi:
                return
            if lo is None or k >= lo:
                yield k, n.v[i]
