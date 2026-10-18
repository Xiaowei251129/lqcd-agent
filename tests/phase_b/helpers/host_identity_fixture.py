"""Scoped, restartable Host UUID providers for C10 exact source fixtures."""
from contextlib import contextmanager
from hashlib import sha256
from importlib import import_module
from types import SimpleNamespace
import uuid

from lqcd_agent.control.strict_json import canonical_bytes


SITES = (
    "lqcd_agent.control.interfaces", "lqcd_agent.control.coordinator",
    "lqcd_agent.control.children", "lqcd_agent.code_agent.external_operation",
)


class HostIdentities:
    def __init__(self, scenario_id, *, ordinals=None):
        assert type(scenario_id) is str and scenario_id
        self.scenario_id = scenario_id
        self.ordinals = dict.fromkeys(SITES, 0) if ordinals is None else dict(ordinals)
        assert set(self.ordinals) == set(SITES)
        assert all(type(n) is int and n >= 0 for n in self.ordinals.values())
        self.allocations = []

    def allocate(self, site):
        self.ordinals[site] += 1
        preimage = {"scenario_id": self.scenario_id, "allocation_site": site, "ordinal": self.ordinals[site]}
        value = uuid.UUID(bytes=sha256(canonical_bytes(preimage)).digest()[:16], version=4)
        self.allocations.append({**preimage, "uuid": str(value)})
        return value

    @contextmanager
    def installed(self):
        originals = {site: import_module(site).uuid for site in SITES}
        try:
            for site in SITES:
                provider = SimpleNamespace(**{k: getattr(uuid, k) for k in dir(uuid) if not k.startswith("__")})
                provider.uuid4 = lambda site=site: self.allocate(site)
                import_module(site).uuid = provider
            yield self
        finally:
            for site, provider in originals.items():
                import_module(site).uuid = provider
