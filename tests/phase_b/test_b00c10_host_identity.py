"""The C10 Host provider exception preserves original allocation functions."""
from hashlib import sha256
from importlib import import_module
import uuid

import pytest

from helpers.host_identity_fixture import HostIdentities, SITES
from lqcd_agent.control.strict_json import canonical_bytes


def test_provider_sequence_is_exact_scoped_and_restartable():
    original_uuid4 = uuid.uuid4
    original_providers = {site: import_module(site).uuid for site in SITES}
    first, second = HostIdentities("identity-meta"), HostIdentities("identity-meta")
    sequences = []
    for allocator in (first, second):
        with allocator.installed():
            values = [str(import_module(site).uuid.uuid4()) for site in SITES for _ in range(2)]
            assert uuid.uuid4 is original_uuid4
            sequences.append(values)
        assert all(import_module(site).uuid is provider for site, provider in original_providers.items())
    assert sequences[0] == sequences[1] and len(set(sequences[0])) == 8
    for row in first.allocations:
        expected = uuid.UUID(bytes=sha256(canonical_bytes({k: row[k] for k in
            ("scenario_id", "allocation_site", "ordinal")})).digest()[:16], version=4)
        assert str(expected) == row["uuid"]
    restarted = HostIdentities("identity-meta", ordinals=first.ordinals)
    with restarted.installed():
        values = [str(import_module(site).uuid.uuid4()) for site in SITES]
    assert not set(values) & set(sequences[0])
    foreign = HostIdentities("foreign-scenario")
    with foreign.installed():
        assert str(import_module(SITES[0]).uuid.uuid4()) not in sequences[0]


def test_exception_restores_every_module_and_global_provider():
    originals = {site: import_module(site).uuid for site in SITES}
    with pytest.raises(RuntimeError):
        with HostIdentities("exception").installed():
            import_module(SITES[0]).uuid.uuid4()
            raise RuntimeError("fixture interruption")
    assert all(import_module(site).uuid is provider for site, provider in originals.items())
