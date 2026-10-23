"""Run the unchanged oMLX external-endpoint benchmark against localhost:8001."""
import asyncio
import hashlib
import json
import logging
import sys
import types
import uuid
import os
from pathlib import Path

from omlx.admin import benchmark
from omlx.utils.proc_memory import get_lifetime_max_phys_footprint

logging.basicConfig(level=logging.INFO)
arm, trial, server_pid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
# Keep the benchmark's unique-prefix cache isolation while pairing exact inputs
# across fresh baseline/candidate servers. Only UUID generation is deterministic.
counter = 0

def paired_uuid():
    global counter
    counter += 1
    raw = hashlib.sha256(f'omlx-ab-20261022:{trial}:{counter}'.encode()).digest()[:16]
    return uuid.UUID(bytes=raw)

benchmark.uuid = types.SimpleNamespace(uuid4=paired_uuid)
observations = []
BaseClient = benchmark.ExternalAPIClient

class RecordedClient(BaseClient):
    async def stream_chat_completion(self, **kwargs):
        stats = await super().stream_chat_completion(**kwargs)
        observations.append({
            'prompt_sha256': hashlib.sha256(json.dumps(kwargs['messages'], sort_keys=True).encode()).hexdigest(),
            'output_sha256': hashlib.sha256(stats.text.encode()).hexdigest(),
            'prompt_tokens': stats.prompt_tokens,
            'completion_tokens': stats.completion_tokens,
            'cached_tokens': stats.cached_tokens,
        })
        return stats

benchmark.ExternalAPIClient = RecordedClient

async def main():
    request = benchmark.BenchmarkRequest(
        model_id='qwen3.8-27b', prompt_lengths=[1024, 4096],
        generation_length=256, batch_sizes=[2, 4], context_profile='code_python',
        external={'base_url': 'http://127.0.0.1:8000/v1', 'model': 'qwen3.8-27b', 'api_key': json.loads((Path.home()/'.omlx/settings.json').read_text())['auth']['api_key'], 'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}},
    )
    run = benchmark.create_run(request)
    await benchmark.run_benchmark(run, None)
    assert run.status == 'completed', run.error_message
    assert len(run.results) == 4 and len(observations) == 9
    assert run.upload_state['skipped_reason'] == 'external_endpoint'
    for row in run.results:
        assert row.get('gen_tps' if row['test_type'] == 'single' else 'tg_tps') is not None and row.get('e2e_latency_s', row.get('total_time_s', 0)) >= 0
    result = {
        'arm': arm, 'trial': trial, 'method': 'omlx.admin.benchmark.run_benchmark(external)',
        'benchmark_source_sha256': hashlib.sha256(Path(benchmark.__file__).read_bytes()).hexdigest(),
        'request': {'prompt_lengths': [1024, 4096], 'generation_length': 256, 'batch_sizes': [2, 4], 'context_profile': 'code_python', 'warmup_mode': 'quick'},
        'results': run.results, 'observations': observations,
        'server_lifetime_peak_phys_footprint_bytes': get_lifetime_max_phys_footprint(server_pid),
        'upload_state': run.upload_state,
    }
    print(json.dumps(result), flush=True)

asyncio.run(main())
