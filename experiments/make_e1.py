# E1: main grid — 11 controllers x 4 widths x 5 service-time laws x 3 seeds, 2x overload, S=10 ms, 600 s
algos = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'delta', 'static', 'failsafe']
with open('e1_jobs.txt', 'w') as f:
    for seed in [1, 2, 3]:
        for c in [4, 16, 64, 256]:
            for dist in ['det', 'ln05', 'exp', 'ln1', 'par25']:
                for a in algos:
                    tag = f'e1:{a}:{c}:{dist}:{seed}'
                    if a == 'failsafe':
                        cmd = f'build/limsim {c} 10 {dist} 2.0 600 {seed}'
                    else:
                        extra = f' static={c}' if a == 'static' else ''
                        cmd = f'java -Xmx2g -cp build Sim {a} {c} 10 {dist} 2.0 600 {seed}{extra}'
                    f.write(f'{tag}\t{cmd}\n')
