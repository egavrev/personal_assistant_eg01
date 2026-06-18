# src/corrections.py  — CORRECTOR read-side: past corrections become prompt context.
def build_corrections_context(store, sender_ref: str, max_n: int) -> str:
    """CORRECTOR read-side: turn past corrections into prompt text the classifier respects.
    Sender-specific corrections first, then recent global, capped at max_n."""
    recent = store.get_recent_corrections(sender_ref=sender_ref, limit=max_n)
    if not recent:
        return ""
    lines = []
    for c in recent:
        lines.append(
            f'- From "{c.get("sender_ref","?")}" re "{c.get("subject_hint","")}": '
            f'I changed {c["field"]} from "{c["ai_value"]}" to "{c["your_value"]}".'
        )
    return "\n".join(lines)
