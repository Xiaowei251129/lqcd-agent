from __future__ import annotations
from typing import Any
AnalysisState = dict[str, Any]

def _human_decision(state: AnalysisState) -> str | None:
    if state.get('human_response_status') != 'consumed':
        return None
    decision = state.get('human_response_decision')
    return decision if isinstance(decision, str) else None

def classify_memory_update(state: AnalysisState) -> dict[str, Any]:
    """Classify the current run without using memory as scientific truth."""
    decision = _human_decision(state)
    risk_level = state['risk_level']
    recommended_action = state['recommended_action']
    if decision == 'reject_or_hold':
        memory_status = 'rejected'
        reason = 'A valid human decision rejected or held the result.'
    elif decision == 'approve_with_conditions':
        memory_status = 'accepted'
        reason = 'A valid human decision approved reporting with conditions.'
    elif risk_level == 'low' and recommended_action == 'accept_mock_result' and (not state['human_approval_required']):
        memory_status = 'accepted'
        reason = 'Low-risk mock result is eligible for accepted memory.'
    else:
        memory_status = 'pending'
        reason = 'Result is not eligible for accepted memory without a low-risk decision or valid human approval.'
    return {'memory_status': memory_status, 'accepted_result': memory_status == 'accepted', 'human_decision': decision, 'classification_reason': reason}
