"""E4: service-time laws measured from real software and the Azure LLM trace, at their measured mean service times."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, LABEL, good_rel

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
df = load('e4.txt'); assert not df['error'].any(), df[df.error]
p = df['tag'].str.split(':', expand=True); df['law'] = p[2]
df['good'] = good_rel(df, ['law', 'c'])
order = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'envoyScaled', 'failsafe', 'delta', 'static']
order = [o for o in order if o in set(df.ctl)]
laws = ['sqlite', 'regex', 'json', 'markdown', 'llm_code', 'llm_conv']
pd.set_option('display.width', 250)
cell = df.groupby(['ctl', 'law', 'c'])[['util', 'meanLatOverS', 'limitOverC', 'good']].mean().reset_index()
cell.to_csv(os.path.join(OUT, 'e4_cells.csv'), index=False)
for m in ['util', 'meanLatOverS']:
    t = cell.pivot_table(index='ctl', columns=['law', 'c'], values=m).reindex(order)[laws]
    print(f'\n{m}\n', t.round(2).to_string())
    t.round(4).to_csv(os.path.join(OUT, f'e4_{m}.csv'))
summ = df.groupby('ctl').agg(runs=('util', 'size'), util_median=('util', 'median'), util_min=('util', 'min'),
                             lat_median=('meanLatOverS', 'median'), lat_max=('meanLatOverS', 'max'), good_share=('good', 'mean')).reindex(order)
print('\n', summ.round(3).to_string())
summ.round(4).to_csv(os.path.join(OUT, 'e4_summary.csv'))
