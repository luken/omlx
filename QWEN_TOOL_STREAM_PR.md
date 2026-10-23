Qwen tool calls currently withhold argument bodies until the complete envelope arrives. Long code/docstring calls consequently appear idle. This series streams safe argument prefixes through the existing Qwen envelope filter and validates the emitted prefix against native parsing before closing successful JSON. It preserves stable call IDs/indices, native fallback and sibling calls, literal markup, truncation and terminal accounting. Partial JSON must not be executed.

Revives ashhart's closed #3646 with attribution. The first argument fragment is sent promptly; subsequent fragments are coalesced at 512 characters or 200 ms on arrivals, without a background timer. There are no inference, sampling, model, kernel, memory-policy or MTP changes.

Four focused, signed-off commits:

1. `7bff2e0d`: restore admin route getters after fixture teardown (independent test prerequisite, reproduced on unmodified upstream).
2. `e41068a5`: handle incomplete tool calls at the token limit, preserving complete siblings and finish reasons.
3. `fabbe224`: terminal usage/metrics accounting and cancellation cleanup.
4. `bb860929`: validated incremental Qwen tool-argument streaming and regression coverage.

Targets upstream `main`. The series was based and measured on `6aba0dd3`; current main `e3bcfb55` adds two unrelated commits, and a local merge-tree check passes. The benchmarked code is preserved rather than relabeling measurements as a new run against those newer commits.

### Correctness validation

Native Apple Silicon validation of the equivalent final tree: **2,982 focused tests passed**, and the default suite had **19,308 passed, 1,088 skipped, 85 deselected**. The history-only split retained identical final tree `5f115a36db62584b2d93464cb707980bb758e7be`; its truncation and accounting intermediates independently passed 1,276 and 1,287 tests (12 deselected each). Independent reviews resolved shared-envelope sibling compatibility and covered both registered Qwen parsers, literal markup, truncation, bounded queues and cancellation. Generated tool-fixture Python was compiled, never executed.

### Primary performance comparison — 2026-10-22

Patch-series update (2026-10-22): the current four-patch head is `bb860929`.
The previous truncation/accounting prerequisite was split into `e41068a5`
(token-limit truncation) and `fabbe224` (usage/metrics/cancellation). Its final
Git tree is identical to the benchmarked `fb8ba8e4` tree; measurements below
were collected before that history-only split and still describe the same code.

Benchmarked upstream `6aba0dd3` against the exact three-patch head `fb8ba8e4`
on Apple M4 Pro / 48 GiB. Both were freshly built and installed as wheels,
using identical official 0.7.2 native kernels and dependencies. Native kernels
were not rebuilt: their source/build configuration is unchanged, and this host
has no Metal compiler. Installed-package hashes and active kernel availability
were verified.

Model: `Jundot/Qwen3.8-27B-oQ4e-mtp` revision `49c1d603`, TQ4 skip-last,
Lightning MTP adaptive maximum depth 4, reasoning off, request temperature 0,
balanced memory guard and 4 GB write-through hot cache. Six alternating paired
trials used fresh service processes/private caches, identical prompts, and the
unchanged upstream `omlx.admin.benchmark` external-endpoint runner. No leaderboard
upload. All 96 measured ordinary responses generated 256 tokens; cache hits were
zero. Requested prompt lengths differ from actual counts (~1.16K/~4.37K).

| Workload | Main median latency, s | Patched, s | Latency change | Decode change |
| --- | ---: | ---: | ---: | ---: |
| Serial requested pp1024 | 16.730 | 16.821 | +0.54% | −1.20% |
| Serial requested pp4096 | 43.085 | 43.218 | +0.31% | −0.50% |
| Batch 2, requested pp1024 | 35.197 | 34.858 | −0.96% | +1.97% |
| Batch 4, requested pp1024 | 68.033 | 68.167 | +0.20% | +3.05% |

No consistent material end-to-end regression was observed in these workloads.
This does not establish zero overhead or statistical equivalence. Individual
paired latency changes ranged from −5.26% to +9.23%. Decode outliers include
−24.17% in the first batch-of-two pair and −13.00% in the final batch-of-four
pair; both include differing output hashes and MTP handoff/calibration sequences.
Their cause is not isolated. Hashes match in 7/12 serial and 28/36 batch pairs,
so exact ordinary-output equivalence is not claimed. External prefill rates are
TTFT-derived proxies. Median lifetime physical peak after ordinary workloads:
20.915 → 20.886 GiB (−0.14%); this excludes the later tool check's peak.

All twelve exact-copy tool calls produced identical JSON arguments containing a
compileable Python module with a 450-word docstring: 945 prompt / 636 completion
tokens, no cache hits or reasoning tokens, stable call identity/index. Code was
compiled but not executed. Median total response: **17.494 → 17.538 s (+0.25%)**.
First argument fragment longer than one character: **17.494 → 8.909 s (49.07%
earlier)**; this can include JSON field framing. Native generation: 69.225 →
69.195 tok/s (−0.04%). Earlier streaming increases SSE events **6 → 43** and
wire bytes **4,656.5 → 12,030 (+158.35%)**. CPU/parser cost was not separately
profiled. Quick eight-token warmup does not guarantee every kernel shape was warm.

The six pairs cover this model/hardware, prompts up to ~4.4K and concurrency up
to four, not full context, all envelope sizes, other hardware/models or
Anthropic/Responses throughput. Public raw timings, paired differences, summaries and harnesses are linked below. Full private operational receipts and server logs remain retained separately and are not included in the public bundle.

### Earlier comparison — 2026-10-21 (different source snapshot)

Four alternating pairs compared upstream `8b7e7018` with candidate `41306a15`, using the same M4 Pro/48 GiB and dense 27B four-bit model, official 0.7.1 kernels, fresh processes/caches and the upstream external benchmark. These runs generated 128 tokens, so their absolute timings are not directly comparable with the 256-token primary study.

| Workload | Main median latency, s | Patched, s | Latency change | Decode change |
| --- | ---: | ---: | ---: | ---: |
| Serial requested pp1024 | 13.235 | 13.279 | +0.34% | +0.82% |
| Serial requested pp4096 | 38.079 | 37.650 | −1.12% | −2.88% |
| Batch 2, requested pp1024 | 28.628 | 28.715 | +0.30% | −1.02% |
| Batch 4, requested pp1024 | 55.873 | 55.636 | −0.43% | +0.06% |

Median ordinary-workload lifetime memory peak: 21.30 GiB in both arms (+0.01%). All serial output hashes matched; four concurrent outputs differed. Two additional alternating exact-copy tool pairs produced identical output hashes and token counts: total response 15.334 → 15.228 s (−0.69%); first argument fragment longer than one character 15.334 → 8.254 s (46.17% earlier); native generation 82.005 → 83.170 tok/s (+1.42%); SSE events 6 → 26; wire bytes 4,657 → 8,649. Exploratory free-form probes showed earlier argument delivery but different outputs; their completion times are confounded and are not used as performance evidence.

### Reproduction and raw evidence

[Raw benchmark data, summaries, checksums and reproduction harnesses](https://github.com/luken/omlx/tree/95fa5e61637a0fa97f93e15ca94bc05117162ce1/benchmark-evidence).

The evidence contains per-arm benchmark/tool JSON, calculation summaries, exact source identities, harnesses and SHA-256 file checksums. It is kept on a separate evidence branch, outside this feature diff. Run baseline and candidate separately with identical settings and fresh caches; alternate their order. The primary harness invokes unchanged `omlx.admin.benchmark.run_benchmark` in external-endpoint mode with requested prompt lengths `[1024,4096]`, generation length `256`, batch sizes `[2,4]`, `code_python` context and quick warmup. See the evidence README for commands and limitations.

This contribution was AI-assisted and independently reviewed. No zero-overhead, statistical-equivalence, full-context, Flash Next/oQ8e, other-hardware or Anthropic/Responses throughput claim is made.
