"""Marker module added to test Forge/Pulse live re-indexing."""


def reconcile_duplicate_claims(claims):
    """Detect and collapse duplicate insurance claims that share the same
    policy number and incident date, keeping the earliest submission.

    This is a Forge freshness probe added on 2026-06-27 to confirm that
    pushing a commit causes Pulse to re-embed the changed file.
    """
    seen = {}
    for claim in claims:
        key = (claim["policy_number"], claim["incident_date"])
        if key not in seen or claim["submitted_at"] < seen[key]["submitted_at"]:
            seen[key] = claim
    return list(seen.values())
