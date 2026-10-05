# E4: real service-time laws (measured handlers + Azure LLM trace), realistic mean service times
import os
LAWS = {'markdown': 5.659, 'json': 3.168, 'sqlite': 0.217, 'regex': 0.170, 'llm_code': 1348.438, 'llm_conv': 6622.453}
ALGOS = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'delta', 'static', 'failsafe']
with open('e4_jobs.txt', 'w') as f:
    for law, S in LAWS.items():
        for c in [16, 64]:
            dur = (120 if c == 16 else 60) if S < 1 else (600 if S < 100 else int(2000 * S / 1000))
            for seed in [1, 2, 3]:
                for a in ALGOS:
                    tag = f'e4:{a}:{law}:{c}:{seed}'
                    if a == 'failsafe':
                        cmd = f'build/limsim {c} {S} file:data/svc_{law}.txt 2.0 {dur} {seed}'
                    else:
                        extra = f' static={c}' if a == 'static' else ''
                        cmd = f'java -Xmx2g -cp build Sim {a} {c} {S} file:data/svc_{law}.txt 2.0 {dur} {seed}{extra}'
                    f.write(f'{tag}\t{cmd}\n')
print(sum(1 for _ in open('e4_jobs.txt')))

# E4b: Envoy with its update window scaled to the service time (10 x mean) for the two LLM laws
with open('e4b_jobs.txt', 'w') as f:
    for law in ['llm_code', 'llm_conv']:
        S = LAWS[law]
        for c in [16, 64]:
            dur = int(2000 * S / 1000)
            for seed in [1, 2, 3]:
                f.write(f'e4:envoyScaled:{law}:{c}:{seed}\tjava -Xmx2g -cp build Sim envoy {c} {S} file:data/svc_{law}.txt 2.0 {dur} {seed} envoyWin={round(10 * S, 3)}\n')
print('e4b', sum(1 for _ in open('e4b_jobs.txt')))
