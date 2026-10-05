"""E7: theory vs full simulation of the real library code."""
import sys, os, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'theory'))
from load import load
import theory as T

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
os.makedirs(OUT, exist_ok=True)
df = load('e7.txt'); assert not df['error'].any()

# (a) Vegas / Gradient2 per-sample equilibria at c = 256 (collapse regime)
rows = []
for dist in ['det', 'ln05', 'exp', 'ln1', 'ln15', 'par25']:
    sim_v = df[(df.tag.str.startswith('e7a:vegas:')) & (df.dist == dist)]['meanLimit']
    sim_g = df[(df.tag.str.startswith('e7a:g2:')) & (df.dist == dist)]['meanLimit']
    pv = T.vegas_rule_level(dist, 600_000)
    pg = T.g2_per_sample_equilibrium(dist)
    rows.append({'law': dist, 'cv': round(T.cv(dist), 2),
                 'vegas_pred': round(pv, 2), 'vegas_sim_mean': round(sim_v.mean(), 2), 'vegas_sim_sd': round(sim_v.std(), 2),
                 'g2_pred_Lstar': round(pg['Lstar'], 1), 'g2_pred_clamped': round(pg['Lclamped'], 1),
                 'g2_sim_mean': round(sim_g.mean(), 1), 'g2_sim_sd': round(sim_g.std(), 1)})
ta = pd.DataFrame(rows)
print('(a) per-sample equilibria at c = 256 (limit, requests)\n', ta.to_string(index=False))
ta.to_csv(os.path.join(OUT, 'e7a_equilibria.csv'), index=False)

# (b) Gradient2 + WindowedLimit drift: simulated trajectory (time series) vs recursion
tsdir = os.path.join(os.path.dirname(__file__), '..', 'results', 'ts')
rowsb = []
for c in [8, 64]:
    sims = []
    for seed in [1, 2, 3]:
        f = os.path.join(tsdir, f'e7b_g2W_{c}_{seed}.csv')
        if os.path.exists(f): sims.append(pd.read_csv(f)['limit'].values)
    sim = np.mean(np.vstack([s[:3599] for s in sims]), axis=0)
    ode = T.g2w_drift(c, T=3600)
    for t in [300, 600, 900, 1200, 1800, 2400, 3000, 3599]:
        rowsb.append({'c': c, 't_s': t, 'sim_limit': round(float(sim[t - 1]), 1), 'pred_limit': round(float(ode[t - 1]), 1),
                      'rel_err': round(float(ode[t - 1] / sim[t - 1] - 1), 3)})
tb = pd.DataFrame(rowsb)
print('\n(b) Gradient2+window drift (mean of 3 seeds) vs recursion\n', tb.to_string(index=False))
tb.to_csv(os.path.join(OUT, 'e7b_drift.csv'), index=False)

# (d) Delta: elasticity curve at a frozen limit, and SD law
rowsd = []
for dist in ['det', 'exp', 'ln1']:
    for x in [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40]:
        r = df[df.tag == f'e7d:curve:{dist}:{x}']
        if len(r):
            rowsd.append({'law': dist, 'L_over_c': x, 'e_sim': round(float(r.eMean.iloc[0]), 3),
                          'e_theory': round(T.delta_elasticity(x), 3), 'sd_sim': round(float(r.eSd.iloc[0]), 3)})
td = pd.DataFrame(rowsd)
print('\n(d1) elasticity curve\n', td.pivot(index='L_over_c', columns='law', values='e_sim').assign(theory=td.drop_duplicates('L_over_c').set_index('L_over_c')['e_theory']).to_string())
td.to_csv(os.path.join(OUT, 'e7d_curve.csv'), index=False)
rowss = []
for dist in ['det', 'exp', 'ln1', 'par25']:
    for n in [50, 100, 200, 400, 800]:
        r = df[df.tag == f'e7d:sd:{dist}:{n}']
        if len(r):
            cvr = float(r.cvR.iloc[0])
            rowss.append({'law': dist, 'n': n, 'cvR': round(cvr, 3), 'sd_sim': round(float(r.eSd.iloc[0]), 4),
                          'sd_pred': round(T.delta_sd(cvr, n), 4), 'e_mean': round(float(r.eMean.iloc[0]), 3)})
ts_ = pd.DataFrame(rowss); ts_['ratio'] = (ts_.sd_sim / ts_.sd_pred).round(3)
print('\n(d2) SD law (L = 1.4c: both phases above the knee)\n', ts_.to_string(index=False))
ts_.to_csv(os.path.join(OUT, 'e7d_sdlaw.csv'), index=False)
