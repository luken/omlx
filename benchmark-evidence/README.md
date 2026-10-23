# Qwen incremental tool streaming: paired benchmark evidence

These are historical measurements, not a current deployment status report.
The feature branch is `codex/qwen-tool-stream-submit-20261021` at `bb860929`.
Its tree exactly matches measured head `fb8ba8e4` (tree `5f115a36db62584b2d93464cb707980bb758e7be`).

| Study | Baseline | Candidate actually measured | Ordinary pairs | Generation length |
| --- | --- | --- | ---: | ---: |
| 2026-10-21 | `8b7e7018` | `41306a15` | 4 | 128 |
| 2026-10-22 | `6aba0dd3` | `fb8ba8e4` | 6 | 256 |

Both used Apple M4 Pro / 48 GiB, dense `Jundot/Qwen3.8-27B-oQ4e-mtp` revision
`49c1d60367d976a730a725ea3bbed32a8e94b878`, TQ4 skip-last, Lightning MTP
adaptive depth 4, reasoning off, temperature 0 and 4 GB write-through hot cache.
Fresh processes and private caches; alternating order; zero measured cache hits.
The earlier study used isolated source servers and official 0.7.1 kernels.
The primary study used freshly built/installed Python wheels and identical official 0.7.2
kernels/dependencies. The Metal compiler was unavailable; native kernels were not
rebuilt, and their source/build configuration was unchanged.

The primary study found ordinary median latency changes from -0.96% to +0.54%,
exact-copy tool total +0.25%, first argument fragment longer than one character
49.07% earlier, and SSE wire bytes +158.35%. Such fragments can include JSON
field framing. These samples do not prove zero overhead or statistical equivalence.
Decode outliers and output differences remain in the raw summaries and PR notes.
Earlier free-form tool probes had different outputs and confounded duration;
use the separate fixed-summary.json for their exact-output counterpart.

## Reproduce the primary study

Use a dedicated Apple Silicon test service, not a production endpoint. Install
baseline and candidate separately with identical dependencies/model settings.
Start each arm freshly with an empty private cache and the same model alias
`qwen3.8-27b` on localhost:8000. The harness reads that user's existing oMLX API
key from ~/.omlx/settings.json; it never writes the key into result JSON.
The harness docstrings retain their historical 8001 labels; actual requests use 8000.

```sh
cd benchmark-evidence/2026-10-22
python run_builtin_benchmark.py main 0 SERVER_PID > 0-main-benchmark.json
python check_fixed_tool.py main 0 > 0-main-tool.json
```

Repeat with candidate, alternating order for six pairs (trial 0..5), replacing
SERVER_PID with the current arm's PID. The ordinary harness uses the unchanged
upstream external-endpoint benchmark, requested prompt lengths 1024/4096,
generation 256, batch 2/4, code_python context and quick 8-token warmup. It pairs
UUID-derived prompt prefixes and records returned hashes/counts without changing
timing calculations. Actual prompt counts differ from requested lengths.
The fixed-output harness compiles generated Python but does not execute it.

Run analyze.py in the directory containing the primary per-arm JSON to reproduce
summary.json. All published data/harness files are enumerated in SHA256SUMS.json.
No private service configuration, keys, endpoint credentials or server logs are
included. This evidence branch is intentionally separate from the feature diff.
