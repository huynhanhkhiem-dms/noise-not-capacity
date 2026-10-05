"""E1 main grid: per-controller summaries and the 'good-region' score."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, LABEL, good_rel

df = load('e1_main.txt')
assert not df['error'].any(), df[df['error']]
df['good'] = good_rel(df, ['c', 'dist'])
order = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'failsafe', 'delta', 'static']
g = df.groupby('ctl')
summ = pd.DataFrame({
    'runs': g.size(),
    'util_median': g['util'].median(),
    'util_min': g['util'].min(),
    'lat_median': g['meanLatOverS'].median(),
    'lat_max': g['meanLatOverS'].max(),
    'limitOverC_median': g['limitOverC'].median(),
    'good_share': g['good'].mean(),
}).loc[order]
summ.index = [LABEL[i] for i in summ.index]
pd.set_option('display.width', 200)
print(summ.round(3).to_string())

# per (controller, c, dist): mean over seeds
cell = df.groupby(['ctl', 'c', 'dist'])[['util', 'meanLatOverS', 'limitOverC', 'excessReject']].mean().reset_index()
os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'results', 'tables'), exist_ok=True)
cell.to_csv(os.path.join(os.path.dirname(__file__), '..', 'results', 'tables', 'e1_cells.csv'), index=False)
summ.to_csv(os.path.join(os.path.dirname(__file__), '..', 'results', 'tables', 'e1_summary.csv'))
# seed dispersion
disp = df.groupby(['ctl', 'c', 'dist'])['util'].std().groupby('ctl').max()
print('\nmax seed-SD of utilisation per controller:\n', disp.round(4).to_string())
for a in ['vegas', 'g2W', 'envoy', 'failsafe', 'delta']:
    t = cell[cell.ctl == a].pivot(index='c', columns='dist', values='util')[['det', 'ln05', 'exp', 'ln1', 'par25']]
    l = cell[cell.ctl == a].pivot(index='c', columns='dist', values='meanLatOverS')[['det', 'ln05', 'exp', 'ln1', 'par25']]
    print(f'\n{LABEL[a]} utilisation (mean of 3 seeds):\n', t.round(3).to_string())
    print(f'{LABEL[a]} mean latency / S:\n', l.round(2).to_string())
