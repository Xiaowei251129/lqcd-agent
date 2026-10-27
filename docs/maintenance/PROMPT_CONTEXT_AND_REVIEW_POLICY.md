# Prompt context and scientific confirmation

This maintenance repairs context handling and an invalid field dependency while preserving the current control protocol, permissions and human-confirmation policy. Milestone results remain in [Current state](../REPO_CURRENT_STATE.md).

## Context handling

The old context builder replaced any payload over 6,000 characters with a truncation notice, removing the task goal, evidence and output-contract instructions while still allowing a provider call.

The single shared builder now uses lossless compact JSON and retains the existing 6,000-character user-context budget. Exactly 6,000 characters is allowed. Larger payloads raise `context_limit_exceeded` before any provider invocation. No automatic summarization, field-dropping, oversized request or retry branch is added; the caller must reduce the supplied context before retrying.

Request construction now sits inside each provider-backed role's existing error handler. Planner and Reviewer preserve failed artifacts; Coordinator preserves its critical/pending result and human-approval requirement. A preflight failure records a failed trace with null request and response, rather than fabricating a call or storing the oversized content in the error message. Successful traces retain their existing request/response structure. Direct request-builder callers receive a `ValueError` subtype for the limit violation.

## Scientific confirmation

The scientific adapter read `risk_level` from a Reviewer schema that does not define or permit that field. Valid reports therefore relied on the adapter's missing-field default to obtain `high` and require approval.

The adapter now states the same Host policy directly: scientific review emits `risk=high`, `category=scientific_review`, and `human_need=approval`. Model confidence and undeclared risk hints cannot lower that floor. The absent-field lookup, conditional routing branch and redundant report reread were removed. Reviewer and control schemas, permissions, budget rules and Human Response validation are unchanged.

## Verification

- The context boundary test round-trips the complete task, including Unicode and JSON escaping, its case inputs and output constraints. It accepts exactly 6,000 characters and rejects the next character.
- All three provider-backed roles are tested with oversized scientific context and a provider that records any attempted invocation. Calls remain zero and errors/traces retain the role's established failure policy.
- Scientific confirmation is tested with a schema-valid missing risk field and an untrusted low-risk hint. The canonical CLI test requires a paused Run, pending approval, high Host risk and no accepted terminal artifact.

The previous live qualification remains evidence for its original application build. This maintenance does not rerun paid API calls or migrate existing Runs. Fresh offline results and their scope are recorded in the current-state document and ignored check reports.
