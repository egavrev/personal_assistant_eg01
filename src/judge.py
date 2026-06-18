def judge_route(confidence: float, threshold: float) -> str:
    """Confidence gate. At/above threshold -> auto-classified; below -> human review.
    Returns a status string that is also a valid signals.status value."""
    return "classified" if confidence >= threshold else "needs_review"