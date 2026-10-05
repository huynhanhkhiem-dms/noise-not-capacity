#!/bin/bash
# Re-run every job of the limiters that draw from ThreadLocalRandom (Vegas, Gradient; per-sample and windowed)
# with the harness that seeds ThreadLocalRandom from the run seed. Previous (wall-clock-seeded) results are kept
# in results/unseeded/ for comparison. Other controllers are unaffected (checked bit-for-bit).
cd "$(dirname "$0")/.."
if [ -d build_seeded ]; then mv build build_unseeded && mv build_seeded build; fi
mkdir -p results/unseeded
python3 - <<'PY'
import os, re
pat = re.compile(r'^TAG e[0-9a-z]+:(vegas|vegasW|grad|gradW):')
for f in ['e1_main', 'e2', 'e3', 'e4', 'e6', 'e7', 'e8', 'e9sim']:
    p = f'results/{f}.txt'
    if not os.path.exists(p): continue
    lines = open(p).readlines()
    moved = [l for l in lines if pat.match(l)]
    kept = [l for l in lines if not pat.match(l)]
    if not os.path.exists(f'results/unseeded/{f}.txt'):
        open(f'results/unseeded/{f}.txt', 'w').writelines(moved)
    open(p, 'w').writelines(kept)
    print(f, 'moved', len(moved), 'kept', len(kept))
PY
python3 experiments/run.py experiments/e1_jobs.txt results/e1_main.txt 2 >> results/rerun_seeded_log.txt 2>&1
for e in e2 e3 e6 e7 e8 e9sim e4; do
  python3 experiments/run.py experiments/${e}_jobs.txt results/${e}.txt 2 >> results/rerun_seeded_log.txt 2>&1
done
echo SEEDED_RERUN_DONE >> results/rerun_seeded_log.txt
