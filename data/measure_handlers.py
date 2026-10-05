#!/usr/bin/env python3
"""Measure per-request service-time distributions of four real request handlers on real inputs.

Each handler is a realistic unit of server work; each request draws one input uniformly at random from a
real corpus. Service time = CPU time of the request (time.thread_time_ns), which is insensitive to other
processes on the machine. Output: data/svc_<handler>.txt, one service time (ms) per line.

  markdown : render a PyPI project README (1,500 most-downloaded projects) to HTML (python-markdown)
  json     : parse an npm packument and extract the dependency map of its latest version
  sqlite   : one of 8 parameterised queries on the Chinook sample database (point, range, join, aggregate)
  regex    : search a random pattern in a random CPython standard-library source file
Also derives two trace-based LLM service-time proxies from token counts in the Azure LLM inference trace 2023:
  llm_code, llm_conv : T = a*ContextTokens + b*GeneratedTokens with a = 0.25 ms and b = 30 ms.
The coefficients are explicit modeling assumptions, not measurements from Azure, Splitwise, or a specific accelerator.
Only the distribution shape is used because the harness rescales the mean.
"""
import json, os, random, re, sqlite3, sys, time, glob, csv
import markdown

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, 'raw')
N = int(os.environ.get('NREQ', '20000'))
rng = random.Random(20260921)

def timed(fn, inputs, n=N):
    out = []
    fn(inputs[0])                       # warm-up
    for _ in range(n):
        x = inputs[rng.randrange(len(inputs))]
        t0 = time.thread_time_ns(); fn(x); t1 = time.thread_time_ns()
        out.append((t1 - t0) / 1e6)
    return out

def h_markdown():
    docs = [json.loads(l)['description'] for l in open(os.path.join(RAW, 'pypi_descriptions.jsonl'))]
    docs = [d for d in docs if d.strip()]
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    def f(d): md.reset(); md.convert(d)
    return timed(f, docs)

def h_json():
    files = sorted(glob.glob(os.path.join(RAW, 'npm', '*.json')))
    blobs = [open(p, 'rb').read() for p in files]
    def f(b):
        d = json.loads(b)
        latest = d.get('dist-tags', {}).get('latest')
        v = d.get('versions', {}).get(latest, {})
        return len(v.get('dependencies', {}) or {})
    return timed(f, blobs)

QUERIES = [
    ("SELECT * FROM Customer WHERE CustomerId = ?", lambda r: (r.randint(1, 59),)),
    ("SELECT * FROM Invoice WHERE CustomerId = ? ORDER BY InvoiceDate DESC", lambda r: (r.randint(1, 59),)),
    ("SELECT t.Name, a.Title FROM Track t JOIN Album a ON t.AlbumId = a.AlbumId WHERE a.ArtistId = ?", lambda r: (r.randint(1, 275),)),
    ("SELECT g.Name, COUNT(*) FROM Track t JOIN Genre g ON t.GenreId = g.GenreId GROUP BY g.Name", lambda r: ()),
    ("SELECT c.Country, SUM(i.Total) FROM Invoice i JOIN Customer c ON i.CustomerId = c.CustomerId GROUP BY c.Country ORDER BY 2 DESC", lambda r: ()),
    ("SELECT * FROM Track WHERE Name LIKE ?", lambda r: ('%' + r.choice(['love', 'night', 'blue', 'you', 'rock', 'time']) + '%',)),
    ("SELECT il.* FROM InvoiceLine il JOIN Invoice i ON il.InvoiceId = i.InvoiceId WHERE i.BillingCountry = ?", lambda r: (r.choice(['USA', 'Canada', 'France', 'Brazil', 'Germany']),)),
    ("SELECT e.LastName, COUNT(c.CustomerId), SUM(i.Total) FROM Employee e JOIN Customer c ON c.SupportRepId = e.EmployeeId JOIN Invoice i ON i.CustomerId = c.CustomerId GROUP BY e.EmployeeId", lambda r: ()),
]
def h_sqlite():
    con = sqlite3.connect(os.path.join(RAW, 'Chinook_Sqlite.sqlite'))
    qr = random.Random(7)
    items = list(range(len(QUERIES)))
    def f(i):
        sql, par = QUERIES[i]
        con.execute(sql, par(qr)).fetchall()
    return timed(f, items)

def h_regex():
    import sysconfig
    files = sorted(glob.glob(os.path.join(sysconfig.get_paths()['stdlib'], '*.py')))
    texts = [open(p, encoding='utf-8', errors='ignore').read() for p in files]
    pats = [re.compile(p) for p in [r'def \w+\(self', r'\bimport\s+\w+', r'"""[\s\S]*?"""', r'\d+\.\d+', r'raise \w+Error\(', r'#.*TODO', r'\blambda\b']]
    pr = random.Random(11)
    def f(t): return len(pats[pr.randrange(len(pats))].findall(t))
    return timed(f, texts)

def llm(kind, a=0.25, b=30.0):
    path = os.path.join(HERE, '..', '..', 'data', 'azure', 'data', f'AzureLLMInferenceTrace_{kind}.csv')
    path = os.environ.get('AZURE_LLM_DIR', os.path.join(RAW, 'azure')) + f'/AzureLLMInferenceTrace_{kind}.csv'
    out = []
    with open(path) as f:
        for row in csv.DictReader(f):
            out.append(a * int(row['ContextTokens']) + b * int(row['GeneratedTokens']))
    return out

def write(name, xs, note):
    with open(os.path.join(HERE, f'svc_{name}.txt'), 'w') as f:
        f.write(f'# {note}\n')
        for x in xs: f.write(f'{x:.6f}\n')
    import statistics as st
    m = st.mean(xs); sd = st.pstdev(xs); xs2 = sorted(xs)
    print(f'{name:10s} n={len(xs):6d} mean={m:9.3f}ms cv={sd/m:5.2f} p50={xs2[len(xs2)//2]:8.3f} p99={xs2[int(len(xs2)*0.99)]:9.3f} max={xs2[-1]:9.3f}')

if __name__ == '__main__':
    todo = sys.argv[1:] or ['markdown', 'json', 'sqlite', 'regex', 'llm']
    if 'markdown' in todo: write('markdown', h_markdown(), 'CPU ms: python-markdown render of PyPI READMEs (top-1500 projects)')
    if 'json' in todo:     write('json', h_json(), 'CPU ms: json.loads of npm packuments + latest dependency map')
    if 'sqlite' in todo:   write('sqlite', h_sqlite(), 'CPU ms: 8 parameterised Chinook queries (sqlite3)')
    if 'regex' in todo:    write('regex', h_regex(), 'CPU ms: regex findall over CPython stdlib sources')
    if 'llm' in todo:
        write('llm_code', llm('code'), 'proxy ms: 0.25*ctx + 30*gen, Azure LLM inference trace 2023 (code); coefficients are modeling assumptions')
        write('llm_conv', llm('conv'), 'proxy ms: 0.25*ctx + 30*gen, Azure LLM inference trace 2023 (conversation); coefficients are modeling assumptions')
