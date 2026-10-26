"""Pure lookups over generated, deeply immutable control declarations."""
from ._generated_protocol import PROTOCOL, PROTOCOL_SHA256


def operation_variant(operation_type, operation_variant):
    for operation in PROTOCOL["state_machines"]["control_operation"]["operations"]:
        if operation["operation_type"] == operation_type:
            for variant in operation["variants"]:
                if variant["operation_variant"] == operation_variant:
                    return variant
    raise ValueError("Unknown control operation type or variant")


def allows_edge(operation_type, variant, source, target):
    return (source, target) in operation_variant(operation_type, variant)["success_edges"]
