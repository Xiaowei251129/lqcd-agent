"""Exact scalar boundaries and append validation survive the finite optimization."""
from copy import deepcopy
from decimal import Decimal
import math

import pytest

from lqcd_agent.control.execution import append_record_bytes, replay
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest_value, number
from test_execution_0_4_foundation import bootstrap


def test_digest_requires_exact_lowercase_hex_at_every_position():
    alphabet = "0123456789abcdef"
    for position in range(64):
        for char in [*map(chr, range(128)), "é", "０", "𝟢"]:
            value = "a" * position + char + "a" * (63 - position)
            if char in alphabet:
                assert digest_value(value) == value
            else:
                with pytest.raises(ControlIntegrityError, match="Invalid digest"):
                    digest_value(value)
    class StringSubclass(str):
        pass
    for value in (None, True, 1, b"a" * 64, "", "a" * 63, "a" * 65, StringSubclass("a" * 64)):
        with pytest.raises(ControlIntegrityError, match="Invalid digest"):
            digest_value(value)
    assert digest_value(None, nullable=True) is None


def test_number_preserves_exact_types_modes_and_boundaries():
    limit = 2**53 - 1
    class IntegerSubclass(int):
        pass
    class FloatSubclass(float):
        pass
    for value in (None, True, False, "1", Decimal(1), 1j, IntegerSubclass(1), FloatSubclass(1)):
        for integer in (False, True):
            with pytest.raises(ControlIntegrityError, match="Invalid number type"):
                number(value, integer=integer)
    for value in (0, 1, limit):
        assert number(value) == value
        assert number(value, integer=True) == value
    for value in (0.0, -0.0, 1.5, float(limit)):
        assert number(value) == value
        with pytest.raises(ControlIntegrityError, match="Invalid number type"):
            number(value, integer=True)
    for value in (limit + 1, -(limit + 1), 2**4096, math.nextafter(float(limit), math.inf), math.inf, -math.inf, math.nan, -1):
        with pytest.raises(ControlIntegrityError, match="Non-finite, overflowing or out-of-range number"):
            number(value)
    assert number(-limit, minimum=-limit) == -limit
    with pytest.raises(ControlIntegrityError):
        number(0, minimum=1)


def test_canonical_json_retains_encoding_and_recursive_refusal():
    assert canonical_bytes({"é": [True, None, 1, -1.5]}) == '{"é":[true,null,1,-1.5]}'.encode()
    class StringSubclass(str):
        pass
    class ListSubclass(list):
        pass
    cyclic = []
    cyclic.append(cyclic)
    for value in ((1,), ListSubclass([1]), StringSubclass("a"), {StringSubclass("a"): 1}, {1: "a"}, [2**53], [math.nan], cyclic):
        with pytest.raises(ControlIntegrityError):
            canonical_bytes(value)


def test_append_is_byte_exact_and_rejects_old_and_new_corruption():
    ledger = bootstrap()
    encoded = b""
    for index, record in enumerate(ledger.records, 1):
        encoded = append_record_bytes(encoded, record)
        assert encoded == b"\n".join(replay(ledger.records[:index]).records) + b"\n"
    first = canonical_bytes(ledger.records[0]) + b"\n"
    for prefix in (b" " + first, first[:-1], first.replace(b'"event_index":1', b'"event_index":true')):
        with pytest.raises(ControlIntegrityError):
            append_record_bytes(prefix, ledger.records[1])
    for field, value in (("event_index", True), ("previous_execution_head", "f" * 64), ("policy_digest", "g" * 64)):
        bad = deepcopy(ledger.records[1])
        bad[field] = value
        with pytest.raises(ControlIntegrityError):
            append_record_bytes(first, bad)
