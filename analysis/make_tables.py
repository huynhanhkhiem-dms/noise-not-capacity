"""Build the manuscript tables (markdown) from results/*.txt and results/tables/*.csv.
Every number printed in the manuscript's tables comes from this script (results/md/*.md)."""
import sys, os, math
import numpy as np, pandas as pd
HERE = os.path.dirname(__file__); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'theory'))
from load import load, good_rel, LABEL
import theory as T

ROOT = os.path.join(HERE, '..'); TAB = os.path.join(ROOT, 'results', 'tables'); MD = os.path.join(ROOT, 'results', 'md')
os.makedirs(MD, exist_ok=True)
LAW = {'det': 'deterministic', 'ln05': 'lognormal σ=0.5', 'exp': 'exponential', 'ln1': 'lognormal σ=1', 'ln15': 'lognormal σ=1.5',
       'par25': 'Pareto α=2.5', 'markdown': 'markdown', 'json': 'json', 'sqlite': 'sqlite', 'regex': 'regex',
       'llm_code': 'LLM code', 'llm_conv': 'LLM conversation'}
SHORT = {'vegas': 'Vegas', 'vegasW': 'Vegas+W', 'g2': 'Gradient2', 'g2W': 'Gradient2+W', 'grad': 'Gradient', 'gradW': 'Gradient+W',
         'aimd': 'AIMD', 'envoy': 'Envoy', 'envoyScaled': 'Envoy (10s window)', 'failsafe': 'failsafe-go', 'delta': '**Delta**', 'static': 'Static L=c (oracle)'}

def md(df, path, floatfmt=None):
    cols = list(df.columns)
    lines = ['| ' + ' | '.join(str(c) for c in cols) + ' |', '|' + '---|' * len(cols)]
    for _, r in df.iterrows():
        lines.append('| ' + ' | '.join(str(v) for v in r.values) + ' |')
    s = '\n'.join(lines) + '\n'
    open(os.path.join(MD, path), 'w').write(s)
    print(f'--- {path}\n{s}')
    return s

f2 = lambda x: f'{x:.2f}'; f3 = lambda x: f'{x:.3f}'; f1 = lambda x: f'{x:.1f}'
pct = lambda x: f'{100 * x:.0f}%'

# ---------------- Table 3: Netflix rule-level predictions vs simulation ----------------
ta = pd.read_csv(os.path.join(TAB, 'e7a_equilibria.csv'))
e7 = load('e7.txt')
rows = []
for _, r in ta.iterrows():
    if r.law == 'det': continue
    v = e7[e7.tag.str.startswith('e7a:vegas:') & (e7.dist == r.law)]
    g = e7[e7.tag.str.startswith('e7a:g2:') & (e7.dist == r.law)]
    rows.append({'Law (c = 256)': LAW[r.law], 'CV': f2(r.cv),
                 'Vegas L predicted': f2(r.vegas_pred), 'Vegas L simulated': f'{r.vegas_sim_mean:.2f} ± {r.vegas_sim_sd:.2f}',
                 'Vegas utilisation (sim.)': f3(v.util.mean()),
                 'Gradient2 L predicted': ('cycles' if r.law == 'par25' else f1(r.g2_pred_clamped)),
                 'Gradient2 L simulated': f'{r.g2_sim_mean:.1f} ± {r.g2_sim_sd:.1f}', 'Gradient2 utilisation (sim.)': f3(g.util.mean())})
md(pd.DataFrame(rows), 't3a_persample.md')
tw = pd.read_csv(os.path.join(TAB, 'e2_vegasw_theory.csv'))
t = tw.pivot(index='S_ms', columns='dist', values=['pred_limit_over_c', 'sim_limit_over_c'])
rows = [{'s (ms)': int(S), 'exp: predicted L/c': f3(t.loc[S, ('pred_limit_over_c', 'exp')]), 'exp: simulated L/c': f3(t.loc[S, ('sim_limit_over_c', 'exp')]),
         'lognormal σ=1: predicted': f3(t.loc[S, ('pred_limit_over_c', 'ln1')]), 'lognormal σ=1: simulated': f3(t.loc[S, ('sim_limit_over_c', 'ln1')])} for S in t.index]
md(pd.DataFrame(rows), 't3b_vegasw.md')
tb = pd.read_csv(os.path.join(TAB, 'e7b_drift.csv'))
t = tb.pivot(index='t_s', columns='c', values=['pred_limit', 'sim_limit'])
rows = [{'t (s)': int(ti), 'c=8: recursion (2)': f1(t.loc[ti, ('pred_limit', 8)]), 'c=8: simulated': f1(t.loc[ti, ('sim_limit', 8)]),
         'c=64: recursion (2)': f1(t.loc[ti, ('pred_limit', 64)]), 'c=64: simulated': f1(t.loc[ti, ('sim_limit', 64)])} for ti in t.index]
md(pd.DataFrame(rows), 't3c_g2wdrift.md')

# ---------------- Table 4: Envoy ----------------
du = pd.read_csv(os.path.join(TAB, 'e2_envoy_duty.csv'))
rows = []
for S, g in du.groupby('S_ms'):
    rows.append({'s': (f'{int(S)} ms' if S < 1000 else f'{S / 1000:g} s'), 'minRTT duty cycle π': f'{100 * g.duty_pred.iloc[0]:.2f}%',
                 'predicted loss π(1−3/c)': f'{100 * g.loss_pred.iloc[0]:.1f}', 'measured loss, exp': f'{100 * g[g.dist == "exp"].loss_meas_vs_static.iloc[0]:.1f}',
                 'measured loss, lognormal σ=1': f'{100 * g[g.dist == "ln1"].loss_meas_vs_static.iloc[0]:.1f}'})
md(pd.DataFrame(rows), 't4a_envoy_duty.md')
es = pd.read_csv(os.path.join(TAB, 'e7c_summary.csv'))
rows = [{'Law': LAW[r.law], 'epochs': int(r.epochs), 'rel. SD of m̂: Bahadur': f3(r.rel_sd_pred), 'rel. SD of m̂: measured': f3(r.rel_sd_meas),
         'P(epoch under-utilised): predicted': f3(r.p_under_pred), 'measured (u<0.95)': f3(r.p_under_meas),
         'mean epoch utilisation: predicted': f3(r.util_pred), 'measured': f3(r.util_meas),
         'corr(pred., meas.)': ('—' if pd.isna(r.corr_pred_meas) else f2(r.corr_pred_meas))} for _, r in es.iterrows()]
md(pd.DataFrame(rows), 't4b_envoy_epochs.md')

# ---------------- Table 5: Delta ----------------
tc = pd.read_csv(os.path.join(TAB, 'e7d_curve.csv'))
t = tc.pivot(index='L_over_c', columns='law', values='e_sim')
th = tc.drop_duplicates('L_over_c').set_index('L_over_c')['e_theory']
sd = tc.pivot(index='L_over_c', columns='law', values='sd_sim')
rows = [{'L/c': f'{x:.2f}', 'Theorem 7 (ρ→∞)': f3(th[x]), 'deterministic': f3(t.loc[x, 'det']), 'exponential': f3(t.loc[x, 'exp']),
         'lognormal σ=1': f3(t.loc[x, 'ln1'])} for x in t.index]
md(pd.DataFrame(rows), 't5a_elasticity.md')
ss = pd.read_csv(os.path.join(TAB, 'e7d_sdlaw.csv'))
rows = []
for n in [50, 100, 200, 400, 800]:
    r = {'n': n}
    for law in ['exp', 'ln1', 'par25']:
        x = ss[(ss.law == law) & (ss.n == n)].iloc[0]
        r[f'{LAW[law]}: predicted'] = f3(x.sd_pred); r[f'{LAW[law]}: measured'] = f3(x.sd_sim)
    rows.append(r)
md(pd.DataFrame(rows), 't5b_sdlaw.md')
ab = load('e5.txt'); p = ab.tag.str.split(':', expand=True); ab['variant'], ab['srv'] = p[1], p[2]
rows = []
for v, (d, e) in {'e0.5': (0.1, 0.5), 'e0.65': (0.1, 0.65), 'default': (0.1, 0.8), 'e0.9': (0.1, 0.9), 'd0.05': (0.05, 0.8), 'd0.2': (0.2, 0.8)}.items():
    x = ab[(ab.variant == v)]; pr = T.delta_price(d, e)
    rows.append({'δ': d, 'e*': e, 'L*/c (7)': f3(T.delta_equilibrium(d, e)), 'L/c measured': f3(x.limitOverC.mean()),
                 'utilisation (Prop. 10)': f3(pr['util']), 'utilisation measured': f3(x.util.mean()),
                 'mean RTT/s (Prop. 10)': f3(pr['rtt']), 'mean RTT/s measured': f3(x.meanLatOverS.mean()), 'sd(ê) measured': f2(x.eSd.mean())})
md(pd.DataFrame(rows), 't5c_price.md')

# ---------------- Table 6: main grid ----------------
e1 = load('e1_main.txt'); e1['g'] = good_rel(e1, ['c', 'dist'])
order = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'failsafe', 'delta', 'static']
rows = []
for a in order:
    x = e1[e1.ctl == a]
    rows.append({'Controller': SHORT[a], 'utilisation median (min)': f'{x.util.median():.3f} ({x.util.min():.3f})',
                 'mean RTT/s median (max)': f'{x.meanLatOverS.median():.2f} ({x.meanLatOverS.max():.1f})',
                 'p99 RTT/s median': f'{x.p99OverS.median():.1f}', 'limit/c median': f'{x.limitOverC.median():.2f}',
                 'runs in good region': f'{int(x.g.sum())}/{len(x)}'})
md(pd.DataFrame(rows), 't6_main.md')

# ---------------- Table 7: time scale ----------------
e2 = load('e2.txt'); e2['g'] = good_rel(e2, ['S', 'dist'])
ord2 = ['delta', 'envoy', 'envoyScaled', 'failsafe', 'vegasW', 'g2W', 'static']
rows = []
for a in ord2:
    r = {'Controller': SHORT[a]}
    for S in [1, 10, 100, 1000, 5000]:
        x = e2[(e2.ctl == a) & (e2.S == S)]
        r[(f'{S} ms' if S < 1000 else f'{S // 1000} s')] = f'{x.util.mean():.2f} / {x.meanLatOverS.mean():.2f}'
    r['good'] = f'{int(e2[e2.ctl == a].g.sum())}/30'
    rows.append(r)
md(pd.DataFrame(rows), 't7_timescale.md')

# ---------------- Table 8: dynamics ----------------
e3 = pd.read_csv(os.path.join(TAB, 'e3_summary.csv'))
rows = []
for a in ['delta', 'envoy', 'failsafe', 'vegasW', 'g2W', 'vegas', 'g2', 'static']:
    r = {'Controller': SHORT[a]}
    for sc, name in [('cap', 'capacity 64→32'), ('slow', 'service 2× slower'), ('load', 'load 0.5→2')]:
        x = e3[(e3.scenario == sc) & (e3.ctl == a)].iloc[0]
        st = '—' if not np.isfinite(x.settle1) else f'{x.settle1:.0f}'
        r[f'{name}: util / RTT'] = f'{x.util1:.2f} / {x.lat1:.2f}'
        r[f'{name}: settle (s)'] = st
    x = e3[(e3.scenario == 'load') & (e3.ctl == a)].iloc[0]
    r['limit/c at ρ=0.5'] = f'{x.limc0:.1f}'
    r['peak 1-s RTT after surge'] = f'{x.tlat1:.1f}'
    rows.append(r)
md(pd.DataFrame(rows), 't8a_dynamics.md')
rp = pd.read_csv(os.path.join(TAB, 'e3_ramp.csv')).set_index('ctl')
rows = []
for a in ['delta', 'envoy', 'failsafe', 'vegasW', 'g2W', 'vegas', 'g2', 'static', 'deltaAny']:
    x = rp.loc[a]
    rows.append({'Controller': SHORT[a] if a != 'deltaAny' else 'Delta, first binding rule', 'utilisation (rel.)': f'{x.urel:.3f}', 'mean RTT/s': f'{x.lat:.2f}',
                 'excess rejections': f'{100 * x.xrej:.1f}%', '0.9≤ρ≤1.1: util / RTT': f'{x.urel_band:.3f} / {x.lat_band:.2f}',
                 'peak 10-s RTT/s': f'{x.peak10:.1f}', 'max limit/c': f'{x.limc_max:.1f}'})
md(pd.DataFrame(rows), 't8b_ramp.md')

# ---------------- Table 9: real laws (if available) ----------------
if os.path.exists(os.path.join(ROOT, 'results', 'e4.txt')):
    e4 = load('e4.txt')
    if os.path.exists(os.path.join(ROOT, 'results', 'e4b.txt')):
        e4 = pd.concat([e4, load('e4b.txt')], ignore_index=True)
    e4['law'] = e4.tag.str.split(':').str[2]
    e4['g'] = good_rel(e4, ['law', 'c'])
    laws = ['sqlite', 'regex', 'json', 'markdown', 'llm_code', 'llm_conv']
    rows = []
    for a in ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'envoyScaled', 'failsafe', 'delta', 'static']:
        x = e4[e4.ctl == a]
        if not len(x): continue
        r = {'Controller': SHORT[a]}
        for law in laws:
            y = x[x.law == law]
            r[LAW[law]] = (f'{y.util.mean():.2f} / {y.meanLatOverS.mean():.2f}' if len(y) else '—')
        r['good'] = f'{int(x.g.sum())}/{len(x)}'
        rows.append(r)
    md(pd.DataFrame(rows), 't9_real.md')

# ---------------- Table 10: ablations ----------------
rows = []
names = {'default': 'Delta (default)', 'noSettle': 'no SETTLE stage', 'noDrain': 'no DRAIN stage', 'fixedOrder': 'fixed phase order (−,+)',
         'geoMean': 'geometric instead of arithmetic mean', 'n50': 'n_min = 50', 'n800': 'n_min = 800', 'g0.05': 'γ = 0.05', 'g0.2': 'γ = 0.2'}
for v, nm in names.items():
    r = {'Variant': nm}
    for srv in ['fcfs', 'ps']:
        x = ab[(ab.variant == v) & (ab.srv == srv)]
        r[f'{srv.upper()}: util / RTT'] = f'{x.util.mean():.3f} / {x.meanLatOverS.mean():.2f}'
        r[f'{srv.upper()}: L/c'] = f'{x.limitOverC.mean():.2f}'
        r[f'{srv.upper()}: mean ê'] = f'{x.eMean.mean():.2f}'
    rows.append(r)
md(pd.DataFrame(rows), 't10_ablation.md')

# ---------------- Table 11: load and processor sharing (if available) ----------------
parts = []
if os.path.exists(os.path.join(ROOT, 'results', 'e6.txt')):
    e6 = load('e6.txt')
    e6['g'] = good_rel(e6, ['rho'])
    rows = []
    for a in ['delta', 'envoy', 'failsafe', 'vegasW', 'g2W', 'vegas', 'aimd', 'static', 'deltaAny']:
        r = {'Controller': SHORT.get(a, a) if a != 'deltaAny' else 'Delta, first binding rule'}
        for rho in [0.5, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 3.0, 5.0]:
            x = e6[(e6.ctl == a) & (e6.rho == rho)]
            r[f'ρ={rho:g}'] = f'{x.util.mean() / min(1.0, rho):.2f} / {x.meanLatOverS.mean():.2f}'
        r['good'] = f'{int(e6[e6.ctl == a].g.sum())}/{len(e6[e6.ctl == a])}'
        rows.append(r)
    md(pd.DataFrame(rows), 't11a_load.md')
if os.path.exists(os.path.join(ROOT, 'results', 'e8.txt')):
    e8 = load('e8.txt')
    if len(e8) >= 66:
        e8['g'] = good_rel(e8, ['dist'])
        rows = []
        for a in order:
            x = e8[e8.ctl == a]
            rows.append({'Controller': SHORT[a], 'exp: util / RTT': f'{x[x.dist == "exp"].util.mean():.3f} / {x[x.dist == "exp"].meanLatOverS.mean():.2f}',
                         'lognormal σ=1: util / RTT': f'{x[x.dist == "ln1"].util.mean():.3f} / {x[x.dist == "ln1"].meanLatOverS.mean():.2f}',
                         'good': f'{int(x.g.sum())}/{len(x)}'})
        md(pd.DataFrame(rows), 't11b_ps.md')

# ---------------- Table 12: wall-clock validation (E9) ----------------
if os.path.exists(os.path.join(ROOT, 'results', 'e9.txt')):
    def parse9(path):
        rows = []
        for l in open(path):
            if not l.startswith('TAG '): continue
            p = l.split(); kv = dict(x.split('=', 1) for x in p[3:] if '=' in x); kv['tag'] = p[1]; rows.append(kv)
        d = pd.DataFrame(rows)
        for c in ['limitOverC', 'util', 'meanLatOverS', 'excessReject']: d[c] = pd.to_numeric(d[c])
        d['ctl'] = d.tag.str.split(':').str[1]
        return d
    rt, sm = parse9(os.path.join(ROOT, 'results', 'e9.txt')), parse9(os.path.join(ROOT, 'results', 'e9sim.txt'))
    rows = []
    for a in ['vegas', 'g2W', 'delta']:
        x, y = rt[rt.ctl == a], sm[sm.ctl == a]
        rows.append({'Controller': SHORT[a], 'limit/c: wall clock': f'{x.limitOverC.mean():.3f}', 'limit/c: simulated': f'{y.limitOverC.mean():.3f}',
                     'utilisation: wall clock': f'{x.util.mean():.3f}', 'utilisation: simulated': f'{y.util.mean():.3f}',
                     'mean RTT/s: wall clock': f'{x.meanLatOverS.mean():.3f}', 'mean RTT/s: simulated': f'{y.meanLatOverS.mean():.3f}'})
    md(pd.DataFrame(rows), 't12_wallclock.md')

# ---------------- Table 13: sample size for heavy-tailed laws (E4c) ----------------
if os.path.exists(os.path.join(ROOT, 'results', 'e4c.txt')):
    e4c = load('e4c.txt'); p = e4c.tag.str.split(':', expand=True); e4c['variant'], e4c['law'] = p[1], p[2]
    e4 = load('e4.txt'); e4 = e4[(e4.ctl.isin(['delta', 'static', 'envoy'])) & (e4.tag.str.contains(':json:'))].copy()
    e4['variant'] = e4.ctl.map({'delta': 'delta_n200', 'static': 'static', 'envoy': 'envoy'}); e4['law'] = 'json'
    allr = pd.concat([e4c, e4], ignore_index=True)
    rows = []
    for law, kappa in [('ln15', 2.9), ('json', 4.55)]:
        for v, nm in [('delta_n200', 'Delta, n_min = 200 (default)'), ('delta_n800', 'Delta, n_min = 800'), ('delta_n3200', 'Delta, n_min = 3200'),
                      ('envoy', 'Envoy'), ('static', 'Static L=c (oracle)')]:
            r = {'Law': f'{LAW[law]} (CV {kappa})', 'Controller': nm}
            for c in [16, 64]:
                x = allr[(allr.law == law) & (allr.variant == v) & (allr.c == c)]
                r[f'c={c}: util / RTT'] = (f'{x.util.mean():.3f} / {x.meanLatOverS.mean():.2f}' if len(x) else '—')
                r[f'c={c}: sd(ê)'] = (f'{x.eSd.mean():.2f}' if len(x) and v.startswith('delta') else '—')
            rows.append(r)
    md(pd.DataFrame(rows), 't13_samplesize.md')
