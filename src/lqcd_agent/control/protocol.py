"""Read the packaged control declaration once and expose its immutable values."""
from hashlib import sha256
from importlib.resources import files
from types import MappingProxyType

from .strict_json import loads, require

__all__ = ["PROTOCOL", "PROTOCOL_SHA256", "operation_variant"]


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _load_protocol():
    raw = files(__package__).joinpath("protocol.json").read_bytes()
    protocol = loads(raw, canonical=False)
    require(protocol["state_machines"]["control_operation"]["operations"], "Missing control operations")
    source = next(row for row in protocol["evidence_unions"] if row["union_id"] == "SourceSnapshotProof")
    revisions = source["valid_schema_revision_combinations"]
    require(revisions and all(row["source_schema"] == "0.4" for row in revisions),
            "Invalid source snapshot schema revisions")
    return _freeze(protocol), sha256(raw).hexdigest()


PROTOCOL, PROTOCOL_SHA256 = _load_protocol()


def operation_variant(operation_type, operation_variant):
    for operation in PROTOCOL["state_machines"]["control_operation"]["operations"]:
        if operation["operation_type"] == operation_type:
            for variant in operation["variants"]:
                if variant["operation_variant"] == operation_variant:
                    return variant
    raise ValueError("Unknown control operation type or variant")
