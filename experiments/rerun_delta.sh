#!/bin/bash
# Re-run every Delta job with the final binding rule (build_final -> build), keeping the first-design lines for comparison.
# Non-Delta results are unaffected (the harness changes are additive) and are not re-run.
cd "$(dirname "$0")/.."
while pgrep -f run_all.sh > /dev/null; do sleep 20; done
if [ -d build_final ]; then mv build build_prev && mv build_final build; fi
mkdir -p results/first_design
for f in e1_main e2 e3 e4 e5 e6 e7 e8; do
  [ -f results/$f.txt ] || continue
  if [ ! -f results/first_design/$f.txt ]; then
    grep -E '^TAG (e[0-9]+[a-z]?:delta:|e5:|e7d:)' results/$f.txt > results/first_design/$f.txt
  fi
  grep -vE "^TAG (e[0-9]+[a-z]?:delta:|e5:|e7d:)" results/$f.txt > results/$f.tmp; mv results/$f.tmp results/$f.txt
done
python3 experiments/run.py experiments/e1_jobs.txt results/e1_main.txt 2 >> results/rerun_log.txt 2>&1
for e in e2 e3 e5 e6 e7 e8 e4; do
  python3 experiments/run.py experiments/${e}_jobs.txt results/${e}.txt 2 >> results/rerun_log.txt 2>&1
done
echo RERUN_DONE >> results/rerun_log.txt
