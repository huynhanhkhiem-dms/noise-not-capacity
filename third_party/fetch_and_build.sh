#!/bin/bash
# Fetch the exact third-party revisions used in the paper and build them.
#   Netflix concurrency-limits  78a74b9878d38c4c048b0304ce12a162ab7b7222 (Apache-2.0)
#   failsafe-go                 5759a5e6d557eace215f820f5b5e663d5c05c3ee (MIT)
#   Envoy (reference for port)  b71f63bd875e1df93ea68e04e9fb788dd967a611 (Apache-2.0)
set -euo pipefail
cd "$(dirname "$0")"
TP=$(pwd)
[ -d concurrency-limits ] || git clone -q https://github.com/Netflix/concurrency-limits.git
(cd concurrency-limits && git checkout -q 78a74b9878d38c4c048b0304ce12a162ab7b7222)
[ -d failsafe-go ] || git clone -q https://github.com/failsafe-go/failsafe-go.git
(cd failsafe-go && git checkout -q 5759a5e6d557eace215f820f5b5e663d5c05c3ee && git apply --check ../failsafe_simclock.patch 2>/dev/null && git apply ../failsafe_simclock.patch || true)
mkdir -p ../build
# slf4j API stub (the core module's only dependency; logging is disabled in all experiments)
javac -nowarn -d ../build $(find slf4j-stub -name "*.java") $(find concurrency-limits/concurrency-limits-core/src/main/java -name "*.java")
javac -nowarn -cp ../build -d ../build ../harness/*.java
# failsafe-go simulator (dependencies fetched directly from GitHub)
mkdir -p failsafe-go/cmd/limsim && cp limsim.go failsafe-go/cmd/limsim/main.go
(cd failsafe-go && GOPROXY=direct GOSUMDB=off GOFLAGS=-mod=mod go build -o ../../build/limsim ./cmd/limsim)
echo "built: ../build (Java classes) and ../build/limsim (Go)"
