#!/usr/bin/env python3
"""Generate job lists for experiments E2-E8 (E1 is make_e1.py; E4 needs measured distributions)."""
import os
J = 'java -Xmx2g -cp build Sim'
LS = 'build/limsim'
HERE = os.path.dirname(os.path.abspath(__file__))

def job(f, tag, algo, c, S, dist, rho, dur, seed, extra=''):
    if algo == 'failsafe':
        cmd = f'{LS} {c} {S} {dist} {rho} {dur} {seed} {extra}'.strip()
    else:
        if algo == 'static' and 'static=' not in extra:
            extra = (extra + f' static={c}').strip()
        a = 'envoy' if algo.startswith('envoy') else algo
        cmd = f'{J} {a} {c} {S} {dist} {rho} {dur} {seed} {extra}'.strip()
    f.write(f'{tag}\t{cmd}\n')

MAIN = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'delta', 'static', 'failsafe']

# E2: time-scale sweep (service time 1 ms .. 5 s), c = 64
with open(os.path.join(HERE, 'e2_jobs.txt'), 'w') as f:
    for S in [1, 10, 100, 1000, 5000]:
        dur = max(600, int(2 * S))           # >= 2000 mean service times per half
        for dist in ['exp', 'ln1']:
            for seed in [1, 2, 3]:
                for a in ['envoy', 'envoyScaled', 'failsafe', 'delta', 'vegasW', 'g2W', 'static']:
                    extra = f'envoyWin={max(100, 10 * S)}' if a == 'envoyScaled' else ''
                    job(f, f'e2:{a}:{S}:{dist}:{seed}', a, 64, S, dist, 2.0, dur, seed, extra)

# E3: dynamics (capacity step, service slowdown, load step, slow load ramp through rho = 1), c = 64, S = 10 ms, exp; time series
def ramp():
    ch = []
    for k in range(1, 60):                    # 30-s steps: 0.5 -> 1.5 over 900 s, then back to 0.5
        t = 30 * k
        r = 0.5 + (t / 900.0) if t <= 900 else 1.5 - (t - 900) / 900.0
        ch.append(f'{t}:rho:{r:.4f}')
    return ','.join(ch)
SCEN = {'cap': ('2.0', 'change=600:c:32,1200:c:64'),
        'slow': ('2.0', 'change=600:s:2,1200:s:1'),
        'load': ('0.5', 'change=600:rho:2,1200:rho:0.5'),
        'ramp': ('0.5', 'change=' + ramp())}
os.makedirs(os.path.join(HERE, '..', 'results', 'ts'), exist_ok=True)
with open(os.path.join(HERE, 'e3_jobs.txt'), 'w') as f:
    for sc, (rho, ch) in SCEN.items():
        for seed in [1, 2, 3]:
            for a in ['vegas', 'vegasW', 'g2', 'g2W', 'envoy', 'failsafe', 'delta', 'static', 'deltaAny']:
                tag = f'e3:{a}:{sc}:{seed}'
                extra = f'{ch} statFrom=0 ts=results/ts/{tag.replace(":", "_")}.csv' + (' anyReject' if a == 'deltaAny' else '')
                job(f, tag, 'delta' if a == 'deltaAny' else a, 64, 10, 'exp', rho, 1800, seed, extra)

# E5: Delta ablations, c = 64, S = 10 ms
VARIANTS = {'default': '', 'd0.05': 'd=0.05', 'd0.2': 'd=0.2', 'e0.5': 'eStar=0.5', 'e0.65': 'eStar=0.65', 'e0.9': 'eStar=0.9',
            'n50': 'nMin=50 nPerL=0', 'n800': 'nMin=800 nPerL=0', 'g0.05': 'gamma=0.05', 'g0.2': 'gamma=0.2',
            'fixedOrder': 'fixedOrder', 'noSettle': 'noSettle', 'noDrain': 'noDrain', 'geoMean': 'geoMean'}
with open(os.path.join(HERE, 'e5_jobs.txt'), 'w') as f:
    for v, ex in VARIANTS.items():
        for server in ['fcfs', 'ps']:
            for dist in ['exp', 'ln1']:
                for seed in [1, 2, 3]:
                    job(f, f'e5:{v}:{server}:{dist}:{seed}', 'delta', 64, 10, dist, 2.0, 600, seed, f'{ex} server={server}')

# E6: load sensitivity, c = 64, exp, S = 10 ms (plus the first-design Delta binding rule as an ablation)
with open(os.path.join(HERE, 'e6_jobs.txt'), 'w') as f:
    for rho in [0.5, 0.8, 1.0, 1.2, 1.5, 3.0, 5.0, 0.9, 1.1]:
        for seed in [1, 2, 3]:
            for a in MAIN:
                job(f, f'e6:{a}:{rho}:{seed}', a, 64, 10, 'exp', rho, 600, seed)
            job(f, f'e6:deltaAny:{rho}:{seed}', 'delta', 64, 10, 'exp', rho, 600, seed, 'anyReject')

# E7: theory validation
with open(os.path.join(HERE, 'e7_jobs.txt'), 'w') as f:
    # (a) Vegas collapse level vs service-time law (c = 256: collapse regime)
    for dist in ['det', 'ln05', 'exp', 'ln1', 'ln15', 'par25']:
        for seed in [1, 2, 3]:
            job(f, f'e7a:vegas:{dist}:{seed}', 'vegas', 256, 10, dist, 2.0, 600, seed)
            job(f, f'e7a:g2:{dist}:{seed}', 'g2', 256, 10, dist, 2.0, 600, seed)
    # (b) Gradient2+WindowedLimit drift trajectories
    for c in [8, 64]:
        for seed in [1, 2, 3]:
            tag = f'e7b:g2W:{c}:{seed}'
            job(f, tag, 'g2W', c, 10, 'exp', 2.0, 3600, seed, f'statFrom=0 ts=results/ts/{tag.replace(":", "_")}.csv')
    # (d) Delta elasticity curve at a frozen limit (gamma = 0) and SD law
    for dist in ['det', 'exp', 'ln1']:
        for x in [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40]:
            L = round(64 * x, 3)
            job(f, f'e7d:curve:{dist}:{x}', 'delta', 64, 10, dist, 2.0, 300, 1, f'gamma=0 initL={L} nPerL=0 nMin=400')
    for dist in ['det', 'exp', 'ln1', 'par25']:
        for n in [50, 100, 200, 400, 800]:
            job(f, f'e7d:sd:{dist}:{n}', 'delta', 64, 10, dist, 2.0, 300, 1, f'gamma=0 initL={round(64*1.4,3)} nPerL=0 nMin={n}')

# E8: processor-sharing server
with open(os.path.join(HERE, 'e8_jobs.txt'), 'w') as f:
    for dist in ['exp', 'ln1']:
        for seed in [1, 2, 3]:
            for a in MAIN:
                job(f, f'e8:{a}:{dist}:{seed}', a, 64, 10, dist, 2.0, 600, seed, 'server=ps')

for e in ['e2', 'e3', 'e5', 'e6', 'e7', 'e8']:
    print(e, sum(1 for _ in open(os.path.join(HERE, f'{e}_jobs.txt'))))

# E7c: Envoy long stationary runs with time series and a log of every minRTT window (per-epoch analysis)
with open(os.path.join(HERE, 'e7c_jobs.txt'), 'w') as f:
    for dist in ['exp', 'ln1', 'ln05', 'ln15', 'par25']:
        for seed in [1, 2, 3]:
            tag = f'e7c:envoy:{dist}:{seed}'
            base = f'results/ts/{tag.replace(":", "_")}'
            job(f, tag, 'envoy', 64, 10, dist, 2.0, 3600, seed, f'statFrom=0 ts={base}.csv epochlog={base}_epochs.csv')
print('e7c', sum(1 for _ in open(os.path.join(HERE, 'e7c_jobs.txt'))))
