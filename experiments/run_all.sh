#!/bin/bash
# Run experiments E7, E2, E3, E5, E6, E8, E4 in sequence (2 workers each). Resumable.
cd "$(dirname "$0")/.."
for e in e7 e2 e3 e5 e6 e8 e4 e7c; do
  python3 experiments/run.py experiments/${e}_jobs.txt results/${e}.txt 2 >> results/run_all_log.txt 2>&1
done
echo ALLDONE >> results/run_all_log.txt
