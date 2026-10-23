"""Validate paired inputs and summarize unmodified upstream benchmark timings."""
import json
import statistics
from pathlib import Path

b = Path(__file__).resolve().parent
trials = 6
rows = {}
peaks = {a: [] for a in ['main', 'candidate']}
tools = {a: [] for a in ['main', 'candidate']}
agreements = {'serial': [0, 0], 'batch': [0, 0], 'warmup': [0, 0]}
observations = []
counts = []
for trial in range(trials):
    arms = {a: json.loads((b / f'{trial}-{a}-benchmark.json').read_text()) for a in peaks}
    assert arms['main']['benchmark_source_sha256'] == arms['candidate']['benchmark_source_sha256']
    for a, d in arms.items():
        assert d['arm'] == a and d['trial'] == trial
        assert len(d['results']) == 4 and len(d['observations']) == 9
        assert d['request']['generation_length'] == 256
        assert d['upload_state']['skipped_reason'] == 'external_endpoint'
        peaks[a].append(d['server_lifetime_peak_phys_footprint_bytes'])
        raw = d['observations']
        assert [r['completion_tokens'] for r in raw] == [8] + [256] * 8
        assert all(r['cached_tokens'] == 0 for r in raw)
        observations.append({'arm': a, 'trial': trial, 'rows': raw})
        counts.extend(raw)
        tool = json.loads((b / f'{trial}-{a}-tool.json').read_text())
        assert tool['valid'] and tool['finish_reason'] == 'tool_calls' and tool['docstring_words'] >= 100
        assert tool['usage']['prompt_tokens_details']['cached_tokens'] == 0
        tools[a].append(tool)
    for indices, label in [(range(1), 'warmup'), (range(1, 3), 'serial'), (range(3, 9), 'batch')]:
        left = sorted([arms['main']['observations'][i] for i in indices], key=lambda r: r['prompt_sha256'])
        right = sorted([arms['candidate']['observations'][i] for i in indices], key=lambda r: r['prompt_sha256'])
        for x, y in zip(left, right):
            assert (x['prompt_sha256'], x['prompt_tokens'], x['completion_tokens']) == (y['prompt_sha256'], y['prompt_tokens'], y['completion_tokens'])
            agreements[label][0] += x['output_sha256'] == y['output_sha256']
            agreements[label][1] += 1
    for x, y in zip(arms['main']['results'], arms['candidate']['results']):
        assert (x['test_type'], x['requested_pp'], x.get('batch_size', 1)) == (y['test_type'], y['requested_pp'], y.get('batch_size', 1))
        key = f"{x['test_type']}-pp{x['requested_pp']}-batch{x.get('batch_size', 1)}"
        rows.setdefault(key, []).append({'trial': trial, 'main': x, 'candidate': y})
    x, y = tools['main'][-1], tools['candidate'][-1]
    assert x['output_sha256'] == y['output_sha256']
    assert (x['usage']['prompt_tokens'], x['usage']['completion_tokens']) == (y['usage']['prompt_tokens'], y['usage']['completion_tokens'])

def compare(left, right):
    assert len(left) == len(right) == trials
    paired = [100 * (y / x - 1) for x, y in zip(left, right)]
    return {'main': left, 'candidate': right, 'main_median': statistics.median(left), 'candidate_median': statistics.median(right), 'median_change_percent': 100 * (statistics.median(right) / statistics.median(left) - 1), 'paired_changes_percent': paired, 'paired_median_change_percent': statistics.median(paired), 'paired_range_percent': [min(paired), max(paired)]}

summary = {'trials': trials, 'ordinary': {}, 'tools': {}, 'output_agreement': agreements, 'observations': observations, 'tool_raw': tools}
for name, values in rows.items():
    metrics = ['pp_tps', 'tg_tps', 'e2e_latency_s', 'avg_ttft_ms'] if values[0]['main']['test_type'] == 'batch' else ['processing_tps', 'gen_tps', 'e2e_latency_s', 'ttft_ms']
    summary['ordinary'][name] = {m: compare([r['main'][m] for r in values], [r['candidate'][m] for r in values]) for m in metrics}
summary['peak_physical_bytes'] = compare(peaks['main'], peaks['candidate'])
for metric in ['seconds', 'first_argument_seconds', 'events', 'wire_bytes', 'argument_fragments', 'generation_tokens_per_second', 'prompt_tokens_per_second']:
    def value(row):
        return row['usage'][metric] if metric.endswith('_per_second') else row[metric]
    summary['tools'][metric] = compare([value(r) for r in tools['main']], [value(r) for r in tools['candidate']])
(b / 'summary.json').write_text(json.dumps(summary, indent=2))
for name, metrics in summary['ordinary'].items():
    print(name)
    for metric, r in metrics.items():
        print(f"  {metric}: {r['main_median']:.3f} -> {r['candidate_median']:.3f} ({r['median_change_percent']:+.2f}%), pairs={[round(v, 2) for v in r['paired_changes_percent']]}")
for name, metrics in [('tool', summary['tools']), ('memory', {'bytes': summary['peak_physical_bytes']})]:
    print(name)
    for metric, r in metrics.items():
        print(f"  {metric}: {r['main_median']:.3f} -> {r['candidate_median']:.3f} ({r['median_change_percent']:+.2f}%), pairs={[round(v, 2) for v in r['paired_changes_percent']]}")
print('Output agreement:', agreements)
