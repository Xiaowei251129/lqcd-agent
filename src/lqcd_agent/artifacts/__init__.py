"""Artifact registry and current-result helpers."""

from lqcd_agent.artifacts.registry import (
    ARTIFACT_SLOTS,
    attempt_output_dir,
    current_artifact_pointer,
    initialize_artifact_registry,
    invalidate_for_target,
    prepare_attempt_output_dir,
    protect_current_artifact,
    register_artifact_bundle,
    register_human_response_snapshot,
    validate_state_artifacts,
)

__all__ = [
    "ARTIFACT_SLOTS",
    "attempt_output_dir",
    "current_artifact_pointer",
    "initialize_artifact_registry",
    "invalidate_for_target",
    "prepare_attempt_output_dir",
    "protect_current_artifact",
    "register_artifact_bundle",
    "register_human_response_snapshot",
    "validate_state_artifacts",
]
