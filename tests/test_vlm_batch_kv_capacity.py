# SPDX-License-Identifier: Apache-2.0
"""Compare the patched generic cache with the installed, unmodified source."""

import importlib.util
import random

import mlx.core as mx
import pytest
from mlx_vlm.models import cache as vlm_cache

import omlx.scheduler  # noqa: F401

spec = importlib.util.spec_from_file_location("_stock_vlm_cache", vlm_cache.__file__)
stock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stock)


def make(module, lengths):
    rows = []
    for row, length in enumerate(lengths):
        c = module.KVCache()
        x = (mx.arange(2 * length * 8).reshape(1, 2, length, 8) % 29 + row).astype(
            mx.bfloat16
        )
        c.update_and_fetch(x, x / 4)
        rows.append(c)
    return module.BatchKVCache.merge(rows)


def equal(a, b):
    for x, y in zip(a.state, b.state):
        if x is None or y is None:
            assert x is y
        else:
            assert x.shape == y.shape
            assert mx.array_equal(x, y).item()
    assert a._idx == b._idx
    if a.keys is None:
        return
    assert b._logical_width() == a.keys.shape[2]
    assert mx.array_equal(a.keys, b.keys[..., : b._logical_width(), :]).item()
    assert mx.array_equal(a.values, b.values[..., : b._logical_width(), :]).item()
    # Include masked padding, stale speculative columns and the actual SDPA.
    q = mx.ones((a.keys.shape[0], 2, 1, 8), mx.bfloat16) / 8
    outputs = []
    for c in (a, b):
        mask = (
            mx.arange(c._idx)[None, None, None, :]
            >= c.left_padding[:, None, None, None]
        )
        outputs.append(
            mx.fast.scaled_dot_product_attention(q, *c.state[:2], scale=0.25, mask=mask)
        )
    assert mx.array_equal(*outputs).item()
    for i in range(a.keys.shape[0]):
        for x, y in zip(a.extract(i).state, b.extract(i).state):
            assert mx.array_equal(x, y).item()


@pytest.mark.parametrize("seed", range(20))
def test_cache_and_attention_match_stock_through_lifecycle(seed):
    rng = random.Random(seed)
    a, b = make(stock, [271, 269, 134]), make(vlm_cache, [271, 269, 134])
    equal(a, b)
    for step in range(40):
        operation = rng.choice(
            ["append", "merge", "trim", "rollback", "filter", "extend", "restore"]
        )
        if operation in ("append", "rollback"):
            n = rng.randint(1, 17)
            x = mx.full((a.keys.shape[0], 2, n, 8), step + 1, mx.bfloat16)
            for c in (a, b):
                c.update_and_fetch(x, x / 4)
            if operation == "rollback":
                padding = [rng.randrange(n) for _ in range(a.keys.shape[0])]
                for c in (a, b):
                    c.prepare(right_padding=padding)
                    c.finalize()
        elif operation == "trim":
            n = min(rng.randint(1, 7), max(0, min(a.offset.tolist()) - 1))
            assert a.trim(n) == b.trim(n)
        elif operation == "merge":
            a = stock.BatchKVCache.merge([a.extract(i) for i in range(a.keys.shape[0])])
            b = vlm_cache.BatchKVCache.merge(
                [b.extract(i) for i in range(b.keys.shape[0])]
            )
        elif operation == "filter":
            kept = rng.sample(range(a.keys.shape[0]), rng.randint(1, a.keys.shape[0]))
            a.filter(kept)
            b.filter(kept)
        elif operation == "extend" and a.keys.shape[0] < 6:
            lengths = [rng.randint(1, 290)]
            a.extend(make(stock, lengths))
            b.extend(make(vlm_cache, lengths))
        elif operation == "restore":
            # The prefix restore contract assigns serialized state to a fresh cache.
            restored = []
            for module, c in ((stock, a), (vlm_cache, b)):
                clone = module.BatchKVCache([0] * c.keys.shape[0])
                clone.state = tuple(mx.array(x) for x in c.state)
                restored.append(clone)
            a, b = restored
        equal(a, b)


def test_merge_reserves_append_without_changing_logical_width():
    c = make(vlm_cache, [8192, 8187])
    assert c._logical_width() == 8192
    capacity = c.keys.shape[2]
    assert 8192 < capacity <= 8192 * 1.125 + 512
    for _ in range(16):
        x = mx.ones((2, 2, 5, 8), mx.bfloat16)
        c.update_and_fetch(x, x)
        assert c.keys.shape[2] == capacity
    row = c.extract(0)
    assert row.keys.shape[2] > row.offset


def test_empty_state_and_idempotent_install():
    from omlx.patches.vlm_batch_kv_capacity import apply_batch_kv_capacity_patch

    c = vlm_cache.BatchKVCache([0, 0])
    c.prepare(right_padding=[1, 0])
    c.finalize()
    assert c.state[:2] == (None, None)
    method = vlm_cache.BatchKVCache.update_and_fetch
    assert apply_batch_kv_capacity_patch()
    assert vlm_cache.BatchKVCache.update_and_fetch is method
