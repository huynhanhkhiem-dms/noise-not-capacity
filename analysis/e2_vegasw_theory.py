"""E2 supplement: windowed VegasLimit, rule-level prediction (theory.vegas_windowed_rule_level) vs simulation."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'theory'))
import theory as T
OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
e2 = pd.read_csv(os.path.join(OUT, 'e2_cells.csv'))
rows = []
cache = {}
old = os.path.join(OUT, 'e2_vegasw_theory.csv')
if '--reuse-pred' in sys.argv and os.path.exists(old):      # predictions depend only on theory.py (seeded); reuse them
    for _, r in pd.read_csv(old).iterrows(): cache[(r.dist, int(r.S_ms))] = r.pred_limit_over_c
for dist in ['exp', 'ln1']:
    for S in [1, 10, 100, 1000, 5000]:
        pred = cache.get((dist, S)) if (dist, S) in cache else sum(T.vegas_windowed_rule_level(dist, 64, S, seed=k) for k in [1, 2, 3]) / 3
        sim = float(e2[(e2.ctl == 'vegasW') & (e2.S == S) & (e2.dist == dist)].limitOverC.iloc[0])
        rows.append({'dist': dist, 'S_ms': S, 'pred_limit_over_c': round(pred, 3), 'sim_limit_over_c': round(sim, 3)})
        print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(os.path.join(OUT, 'e2_vegasw_theory.csv'), index=False)
