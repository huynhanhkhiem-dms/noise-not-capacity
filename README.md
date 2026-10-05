# Noise, Not Capacity

Code, data, experiment definitions, and analysis scripts for:

**Noise, Not Capacity: Closed-Loop Identification of the Saturation Knee in Adaptive Concurrency Limiters**

Author: **Huynh Anh Khiem**  
Faculty of Information Technology, Ton Duc Thang University, Ho Chi Minh City, Vietnam  
ORCID: 0009-0007-7210-174X

## Repository scope

This repository contains the reproducibility materials used in the study. The core experimental inputs are the distributed service-time samples in `data/svc_*.txt`; the experiment harness rescales their means while preserving distributional shape. Public upstream datasets used to construct those samples are documented through provenance scripts and checksum records but are not required to rerun the reported simulations.

The repository intentionally excludes manuscript/submission files and private working material.

## Contents

- `harness/` — deterministic simulated-clock server/limiter harness, Delta implementation, Envoy controller port, and wall-clock validation.
- `tests/` — conformance checks for the Envoy port.
- `third_party/` — pinned-source build script, failsafe-go simulated-clock patch, Go harness, and minimal SLF4J stub.
- `theory/` — analytical checks and rule-level predictions.
- `experiments/` — experiment job lists, generators, and runners.
- `analysis/` — scripts that compute study summaries and figures.
- `data/` — service-time samples actually consumed by the experiments, plus provenance/reconstruction utilities.
- `results/` — reference raw outputs, time series, and compact derived summary tables used to regenerate and verify the reported results.

## Requirements

- Java 21
- Go >= 1.22
- Python 3.11
- Python packages in `requirements.txt`
- Git and network access when pinned third-party sources are fetched

## Quick reproduction

From the repository root:

```bash
third_party/fetch_and_build.sh

javac -cp build -d build_test harness/Envoy.java tests/EnvoyPortTest.java
java -cp build_test EnvoyPortTest

python3 experiments/make_jobs.py

# Fresh rerun of the main experimental grid
python3 experiments/run.py experiments/e1_jobs.txt results/e1_main_reproduced.txt 2

# Regenerate manuscript tables/figures from the packaged reference outputs
python3 analysis/make_tables.py
python3 analysis/figures.py
python3 analysis/headline_sensitivity.py
```

A single Java simulation can be run as:

```bash
java -cp build Sim <algo> <c> <meanMs> <law> <rho> <durS> <seed> [key=value ...]
```

Example:

```bash
java -cp build Sim delta 64 10 exp 2.0 600 1
```

Algorithms include `vegas`, `vegasW`, `g2`, `g2W`, `grad`, `gradW`, `aimd`, `envoy`, `delta`, and `static`. Simulated runs use explicit seeds.

## Reference outputs and fresh reruns

The repository includes the reference raw outputs used for the reported analyses. The analysis scripts regenerate manuscript tables and figures from those reference files. Fresh reruns should be written to a different filename (for example, `*_reproduced.txt`) so the packaged reference outputs remain unchanged and can be compared directly.

## Good-region criterion

For E1, E2, E4, E6, and E8, a run is in the study's good region when its utilization is at least 95% of the mean utilization of the static `L=c` oracle over oracle seeds in the same experimental cell, and its mean RTT is at most 1.5 mean service times. `analysis/load.py` exposes this criterion as `good_rel()`.

## Delta identification scope

The analytical elasticity result is conditional on each fixed-limit arm sampling a stationary saturated regime. The implementation uses rejection during COUNT in both arms as a conservative finite-load update gate. Rejection alone is not claimed to prove stationary saturation.

The frozen-limit E7 validation sets `gamma=0` and records the elasticity estimate from every completed pair before the gate can suppress a base-limit update. SETTLE discards one turnover to reduce phase carry-over; DRAIN keeps the phase limit fixed until measured requests complete.

## Finite-horizon robustness block (E10)

E10 evaluates 120-s runs at worker counts 8, 32, and 128; offered loads 1.3, 2.7, and 4.3; seeds 101, 202, and 303; and six parametric service-time laws. It contains 162 Delta runs and 162 matched static-oracle runs.

The E10 protocol is presented as finite-horizon robustness evidence, not as preregistered or independently confirmatory evidence. The reproducible E10 count is 139/162 good Delta runs. Finite-horizon failures are retained.

Recompute E10 with:

```bash
javac -d build_confirm harness/Delta.java harness/ConfirmSim.java
python3 experiments/run.py experiments/e10_confirm_jobs.txt results/e10_confirm_reproduced.txt 2
python3 analysis/e10_confirm.py results/e10_confirm_reproduced.txt
python3 analysis/e10_effects.py results/e10_confirm_reproduced.txt
```

## Data provenance

The study uses service-time distributions derived from measured request-handler CPU times for Markdown rendering, JSON parsing, SQLite queries, and regex processing, plus two trace-derived LLM proxy distributions from the Azure LLM inference trace 2023.

For the LLM proxies, token counts are mapped as:

`T = 0.25 ms * ContextTokens + 30 ms * GeneratedTokens`.

These coefficients are explicit modeling assumptions used to preserve trace heterogeneity; they are not measurements from Azure or from a specific accelerator.

The simulations use the distributed `data/svc_*.txt` files directly. Provenance and reconstruction utilities are retained under `data/`.

## Third-party components

See `NOTICE` for pinned upstream components, commits, and licenses.

## License

Project code is released under the MIT License. Third-party code and source material retain their original terms as described in `NOTICE`.

## Citation

Citation metadata is provided in `CITATION.cff`.
