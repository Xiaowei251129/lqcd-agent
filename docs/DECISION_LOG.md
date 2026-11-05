# Engineering decisions

These are the reasons for the current design. Implementation and qualification status belong only in [Current state](REPO_CURRENT_STATE.md); [Architecture](ARCHITECTURE.md) describes the system boundaries.

## Research collaboration over one control plane

Use the Python OpenAI Agents SDK for bounded PI/Reviewer tool loops and the sole Codex backend for coding proposals. The SDK supplies model/tool interaction; the existing control plane owns authorization, budgets, leases, cancellation, durable transitions and publication. Do not introduce a second scheduler, session authority or approval mechanism. Admit each model/tool effect before execution, disable transport retries and settle actual effects through the existing resource scope.

Assign scientific framing and implementation planning to one PI. Project preparation produces one versioned method for Code and Reviewer. Review-first and unattended Projects differ at Host admission. The Reviewer examines the actual numerical results in a separate context.



## Empty local assets and attributable reuse

Start user libraries empty inside each installation. Version knowledge, skills and methods with explicit applicability, source references and candidate/reviewed dispositions. Models propose assets; operators review them. Freeze reviewed source bytes atomically into the one coding path, which still delivers a self-contained program. A validation receipt binds evidence to source; registration alone is not execution of that validation or proof of physics correctness.

Persist verified project evidence separately from temporary execution authority. A Project revision supplies context to new Runs; historical copies cannot recover a Run, manufacture acceptance or replace raw-data backups. Keep simple local text/metadata search until measured research needs justify more infrastructure.

## Generated scientific execution and independent assessment

Use the existing planning, CodeHost delivery, fresh Analysis preparation and Scientific Reviewer path for generated calculations. Bind input identity, parameters, sealed code and numerical environment before execution. A completed plan does not imply completed implementation; genuinely pending plans cannot dispatch Code. Preserve one sandbox primitive and one Host numerical-contract implementation for production review and independent assessment.

Keep C2/Normalization hidden calibration and withheld comparisons outside production agents. Failed calibration prevents measured-input assessment. The assessor binds exact program/input/validator identities but has no Run-advancement or scientific-acceptance authority. Keep normal task-authorized tools, networking, automatic SDK permission review and immutable task deadlines; review exact generated source before measured-input qualification. See the [case guide](RESEARCH_CASES.md).

Scalar replica-observable output requires physical definitions, units, kinematics, sample identity and independent arithmetic checks. Host warnings retain the unverified physical suitability and provenance limits. Numerical agreement, model confidence and agreement among agents cannot grant scientific acceptance.

## Evidence and model contracts

Bind scientific input identity to both the frozen Run and the exact stream consumed by calculation, including explicit absence. Replay and fork cannot silently admit replacement data. Model proposals contain scientific content; the Host materializes artifact identities and executable mappings from registered contracts.

Use one Host diagnostic implementation for deterministic and model-assisted review. Models can add interpretation and findings but cannot erase warnings or raise the Host confidence ceiling. Retain complete immutable context bundles, bounded initial views and digest-checked named section reads. Context and retrieved literature remain evidence, not authority. Application assembly owns credentials and live activation.

## Local execution, publication and verification

Qualify native macOS execution under the fixed `/private/tmp` parent and owned local storage. Keep native boot/PID identity, private Hosts, exact publication, lease fences, SQLite WAL/FULL and human confirmation. Linux static, numerical and build checks do not qualify runtime execution. Pure identity/lifecycle/artifact contracts have no I/O; their existing owners retain writes and permissions.

Keep read-only inspection separate from executor assembly. Portable terminal evidence archives are distinct from consistent database backup and Run recovery; verification does not extract or execute them. Reuse immutable ledger snapshots only inside one read or journal validation and refresh after effects. No global replay cache or relaxed durability is justified by the current measurements.

Use one hash-locked environment, installed package resources, narrow static checks and the current behavior-focused test suite. CI publishes only bounded outcome reports with read-only repository access. Historical test counts, build identities and completion narratives remain in Git history rather than parallel maintenance records. See [Verification](VERIFICATION_GUIDE.md) and [Data and security](SECURITY_AND_DATA_POLICY.md).
