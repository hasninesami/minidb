import re


class SQLError(Exception):
    pass


TOK = re.compile(r"\s*(?:(?P<s>'(?:[^']|'')*')|(?P<n>-?\d+(?:\.\d+)?)|(?P<w>[A-Za-z_]\w*)|(?P<o><=|>=|!=|<>|[=<>(),*;]))")
OPS = ('=', '!=', '<>', '<', '>', '<=', '>=')
TYPES = ('INT', 'TEXT', 'REAL')


def lex(q):
    out, p = [], 0
    while 1:
        m = TOK.match(q, p)
        if not m:
            if q[p:].strip():
                raise SQLError(f'bad character near: {q[p:p + 10].strip()!r}')
            return out
        k = m.lastgroup
        out.append((k, m.group(k), m.start(k), m.end(k)))
        p = m.end()


class P:
    def __init__(s, q):
        s.q = q
        s.t = lex(q)
        s.i = 0

    def peek(s):
        return s.t[s.i] if s.i < len(s.t) else (None, None, len(s.q), len(s.q))

    def nxt(s):
        t = s.peek()
        if t[0] is None:
            raise SQLError('unexpected end of input')
        s.i += 1
        return t

    def kw(s, *w):
        t = s.peek()
        if t[0] == 'w' and t[1].upper() in w:
            s.i += 1
            return t[1].upper()

    def need(s, w):
        if not s.kw(w):
            raise SQLError(f'expected {w}')

    def sym(s, c):
        t = s.peek()
        if t[0] == 'o' and t[1] == c:
            s.i += 1
            return True
        return False

    def need_sym(s, c):
        if not s.sym(c):
            raise SQLError(f"expected '{c}'")

    def ident(s):
        t = s.nxt()
        if t[0] != 'w':
            raise SQLError(f'expected a name, got {t[1]!r}')
        return t[1].lower()

    def lit(s):
        k, v = s.nxt()[:2]
        if k == 's':
            return v[1:-1].replace("''", "'")
        if k == 'n':
            return float(v) if '.' in v else int(v)
        if k == 'w' and v.upper() == 'NULL':
            return None
        raise SQLError(f'expected a value, got {v!r}')

    def all(s):
        out = []
        while s.i < len(s.t):
            if s.sym(';'):
                continue
            a = s.peek()[2]
            st = s.stmt()
            out.append((st, s.q[a:s.t[s.i - 1][3]]))
            if s.i < len(s.t) and not s.sym(';'):
                raise SQLError(f'unexpected {s.peek()[1]!r}')
        return out

    def stmt(s):
        w = s.kw('CREATE', 'INSERT', 'SELECT', 'UPDATE', 'DELETE', 'DROP', 'EXPLAIN', 'SHOW')
        if not w:
            raise SQLError(f'unknown statement: {s.peek()[1]!r}')
        return getattr(s, 'p_' + w.lower())()

    def p_explain(s):
        st = s.stmt()
        if st[0] not in ('select', 'update', 'delete'):
            raise SQLError('EXPLAIN works on SELECT, UPDATE, DELETE')
        return ('explain', st)

    def p_show(s):
        s.need('TABLES')
        return ('show',)

    def p_drop(s):
        s.need('TABLE')
        return ('drop', s.ident())

    def p_create(s):
        s.need('TABLE')
        n = s.ident()
        s.need_sym('(')
        cols, pk = [], None
        while 1:
            c = s.ident()
            t = s.ident().upper()
            if t not in TYPES:
                raise SQLError(f'unknown type {t}, use INT, TEXT or REAL')
            if s.kw('PRIMARY'):
                s.need('KEY')
                if pk is not None:
                    raise SQLError('only one PRIMARY KEY allowed')
                pk = len(cols)
            cols.append((c, t))
            if not s.sym(','):
                break
        s.need_sym(')')
        if len({c for c, _ in cols}) < len(cols):
            raise SQLError('duplicate column name')
        return ('create', n, cols, pk)

    def p_insert(s):
        s.need('INTO')
        n = s.ident()
        cl = None
        if s.sym('('):
            cl = [s.ident()]
            while s.sym(','):
                cl.append(s.ident())
            s.need_sym(')')
        s.need('VALUES')
        rows = []
        while 1:
            s.need_sym('(')
            r = [s.lit()]
            while s.sym(','):
                r.append(s.lit())
            s.need_sym(')')
            rows.append(r)
            if not s.sym(','):
                break
        return ('insert', n, cl, rows)

    def p_select(s):
        if s.sym('*'):
            cols = '*'
        elif s.kw('COUNT'):
            s.need_sym('(')
            s.need_sym('*')
            s.need_sym(')')
            cols = 'count'
        else:
            cols = [s.ident()]
            while s.sym(','):
                cols.append(s.ident())
        s.need('FROM')
        n = s.ident()
        w = s.expr() if s.kw('WHERE') else None
        ob = None
        if s.kw('ORDER'):
            s.need('BY')
            ob = (s.ident(), s.kw('ASC', 'DESC') == 'DESC')
        lim = None
        if s.kw('LIMIT'):
            lim = s.lit()
            if type(lim) is not int or lim < 0:
                raise SQLError('LIMIT needs a non-negative integer')
        return ('select', n, cols, w, ob, lim)

    def p_update(s):
        n = s.ident()
        s.need('SET')
        sets = []
        while 1:
            c = s.ident()
            s.need_sym('=')
            sets.append((c, s.lit()))
            if not s.sym(','):
                break
        return ('update', n, sets, s.expr() if s.kw('WHERE') else None)

    def p_delete(s):
        s.need('FROM')
        n = s.ident()
        return ('delete', n, s.expr() if s.kw('WHERE') else None)

    def expr(s):
        a = s.and_()
        while s.kw('OR'):
            a = ('or', a, s.and_())
        return a

    def and_(s):
        a = s.not_()
        while s.kw('AND'):
            a = ('and', a, s.not_())
        return a

    def not_(s):
        if s.kw('NOT'):
            return ('not', s.not_())
        if s.sym('('):
            e = s.expr()
            s.need_sym(')')
            return e
        c = s.ident()
        t = s.nxt()
        if t[0] != 'o' or t[1] not in OPS:
            raise SQLError(f'expected a comparison operator after {c}')
        return ('cmp', c, '!=' if t[1] == '<>' else t[1], s.lit())


def parse(q):
    return P(q).all()
