import argparse
import sys

from db import DB
from sql import SQLError


def fmt(r):
    if r.get('cols'):
        rows = [[('NULL' if v is None else str(v)) for v in x] for x in r['rows']]
        w = [max([len(c)] + [len(x[i]) for x in rows]) for i, c in enumerate(r['cols'])]
        line = '+' + '+'.join('-' * (n + 2) for n in w) + '+'
        print(line)
        print('| ' + ' | '.join(c.ljust(n) for c, n in zip(r['cols'], w)) + ' |')
        print(line)
        for x in rows:
            print('| ' + ' | '.join(v.ljust(n) for v, n in zip(x, w)) + ' |')
        print(line)
    tail = r['msg'] + (f" [{r['plan']}]" if r.get('plan') else '') + f" ({r['ms']} ms)"
    print(tail)


def go(d, sql):
    try:
        for r in d.run(sql):
            fmt(r)
    except SQLError as e:
        print('error:', e)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('script', nargs='?')
    a.add_argument('--db')
    a = a.parse_args()
    d = DB(a.db)
    if a.script:
        with open(a.script) as f:
            go(d, f.read())
    else:
        print('minidb - end statements with ;  (Ctrl+D to quit)')
        buf = ''
        while 1:
            try:
                buf += input('db> ' if not buf else '... ') + '\n'
            except EOFError:
                break
            if buf.rstrip().endswith(';'):
                go(d, buf)
                buf = ''
    d.close()


if __name__ == '__main__':
    main()
