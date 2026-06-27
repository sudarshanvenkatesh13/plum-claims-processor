"""PR probe — added to test Forge/Pulse pull-request ingestion."""


def flag_high_value_claims(claims, threshold=10000):
    """Return claims whose payout amount exceeds `threshold` for manual review.

    Forge PR probe (2026-06-27): verifies that opening a pull request flows
    into Pulse's briefing and teammate-awareness.
    """
    return [c for c in claims if c.get("amount", 0) > threshold]
