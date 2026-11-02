"""Shared deployment limits; input tokens are distinct from generated tokens."""
INPUT_TOKEN_LIMIT = 256_000
COMPACT_RATIO = .8
COMPACT_TOKEN_LIMIT = int(INPUT_TOKEN_LIMIT * COMPACT_RATIO)
