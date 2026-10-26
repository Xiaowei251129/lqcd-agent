# Data and security

Host code owns paths, identities, permissions, leases, transitions, resource settlement and publication. Domain outputs and backend declarations cannot grant authority. External actions need scoped authorization.

Preserve fencing, idempotency, symlink/hardlink checks, private-root ownership, SQLite WAL/FULL, foreign keys, accepted-result immutability, source digests and stop-owner checks. Replay and fork accept current validated sources only.

Keep credentials outside the repository. Mock checks must not enable live providers. The local demo exposes only a fixed synthetic start action on loopback, validates browser origin, and accepts no arbitrary shell command or filesystem root.

Scientific reports must distinguish synthetic and measured inputs, record methods and provenance, and require appropriate scientific review. A passing software or numerical benchmark is not physics acceptance. Do not silently replace raw data, accepted results or failed observations to obtain a pass.
