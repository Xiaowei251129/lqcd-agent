"""Classify a completed research record from verified evidence and actual participation."""


def classify_memory_update(*, complete_evidence, blocked, limitations, authorization_decision=None):
    """Permission decisions are retained facts, never scientific endorsements or rejections."""
    accepted = complete_evidence and not blocked
    outcome = ('qualified' if limitations else 'supported') if accepted else 'inconclusive'
    reason = ('Current Analysis and Review evidence support the recorded conclusion within retained limitations.'
              if accepted else 'The research concluded without sufficient evidence for the requested claim.')
    return {'memory_status': 'accepted' if accepted else 'rejected', 'accepted_result': accepted,
            'scientific_outcome': outcome, 'decision_origin': 'system',
            'authorization_decision': authorization_decision, 'classification_reason': reason}
