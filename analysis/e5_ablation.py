"""E5: Delta ablations and parameter sensitivity (c = 64, s = 10 ms, rho = 2; FCFS and PS; exp and ln1)."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'theory'))
from load import load
import theory as T

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
df = load('e5.txt'); assert not df['error'].any()
p = df['tag'].str.split(':', expand=True)
df['variant'], df['srv'] = p[1], p[2]
order = ['default', 'd0.05', 'd0.2', 'e0.5', 'e0.65', 'e0.9', 'n50', 'n800', 'g0.05', 'g0.2', 'fixedOrder', 'noSettle', 'noDrain', 'geoMean']
order = [o for o in order if o in set(df.variant)]
g = df.groupby(['variant', 'srv'])[['util', 'meanLatOverS', 'limitOverC', 'eMean', 'eSd']].mean()
t = g.unstack('srv').reindex(order)
pd.set_option('display.width', 250)
print(t.round(3).to_string())
t.round(4).to_csv(os.path.join(OUT, 'e5_ablation.csv'))
# predicted equilibrium and price for the parameter variants (saturated, continuous limits)
pred = {}
for v, (d, e) in {'default': (0.1, 0.8), 'd0.05': (0.05, 0.8), 'd0.2': (0.2, 0.8), 'e0.5': (0.1, 0.5), 'e0.65': (0.1, 0.65), 'e0.9': (0.1, 0.9)}.items():
    pr = T.delta_price(d, e)
    pred[v] = {'Lstar_over_c': round(T.delta_equilibrium(d, e), 3), 'util_pred': round(pr['util'], 3), 'rtt_pred': round(pr['rtt'], 3)}
print(pd.DataFrame(pred).T.to_string())
pd.DataFrame(pred).T.to_csv(os.path.join(OUT, 'e5_pred.csv'))
