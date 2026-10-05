#!/usr/bin/env python3
"""Run a list of simulation jobs in parallel and append their RES lines to a results file.

Each job line is:  <tag>\t<command>
 - Java harness:  java -cp build Sim <algo> <c> <meanMs> <dist> <rho> <durS> <seed> [k=v ...]
 - failsafe-go :  build/limsim <c> <meanMs> <dist> <rho> <durS> <seed> [k=v ...]
Jobs whose tag already appears in the results file are skipped (resumable).
usage: run.py jobs.txt results.txt [workers]
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

def main():
    jobs_path, out_path = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            if line.startswith('TAG '):
                done.add(line.split()[1])
    jobs = []
    for line in open(jobs_path):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        tag, cmd = line.split('\t', 1)
        if tag not in done:
            jobs.append((tag, cmd))
    env = dict(os.environ, JAVA_TOOL_OPTIONS='')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def run(job):
        tag, cmd = job
        p = subprocess.run(cmd, shell=True, cwd=root, env=env, capture_output=True, text=True)
        res = [l for l in p.stdout.splitlines() if l.startswith('RES ')]
        return tag, (res[0] if res else 'RES ERROR ' + p.stderr.strip().replace('\n', ' | ')[:300])

    with open(out_path, 'a') as f, ThreadPoolExecutor(workers) as ex:
        for tag, res in ex.map(run, jobs):
            f.write(f'TAG {tag} {res}\n'); f.flush()
    print('done', len(jobs), 'jobs ->', out_path)

if __name__ == '__main__':
    main()
