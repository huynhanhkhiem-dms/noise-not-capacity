"""Sensitivity of good-region headline counts to utilization and mean-RTT thresholds."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, good_rel
parts=[]
for name, keys in [('e1_main.txt',['c','dist']), ('e2.txt',['S','dist']), ('e4.txt',['law','c']), ('e6.txt',['rho']), ('e8.txt',['dist'])]:
    d=load(name)
    if name=='e4.txt': d['law']=d.tag.str.split(':').str[2]
    parts.append((d,keys))
controllers=['delta','envoy','vegasW','failsafe','g2W']
labels={'delta':'Delta','envoy':'Envoy','vegasW':'Vegas+W','failsafe':'failsafe-go','g2W':'Gradient2+W'}
rows=[]
for util_frac in (0.90,0.95,0.98):
    for lat_max in (1.25,1.50,2.00):
        all_rows=[]
        for d,keys in parts:
            x=d[['ctl']].copy(); x['good']=good_rel(d,keys,util_frac=util_frac,lat_max=lat_max); all_rows.append(x)
        a=pd.concat(all_rows,ignore_index=True)
        row={'utilization_fraction_of_oracle':util_frac,'mean_RTT_over_service_time_max':lat_max}
        for ctl in controllers:
            q=a[a.ctl==ctl]['good']; row[labels[ctl]]=f"{int(q.sum())}/{len(q)}"
        rows.append(row)
out=pd.DataFrame(rows)
path=os.path.join(os.path.dirname(__file__),'..','results','tables','headline_sensitivity.csv')
out.to_csv(path,index=False)
print(out.to_string(index=False))
