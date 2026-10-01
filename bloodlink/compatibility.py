"""Medically correct ABO/Rh donor -> recipient compatibility engine.

Compatibility rules (standard transfusion medicine):
  ABO:
    - Group O red cells carry no A/B antigens      -> O can donate to all.
    - Group A carries A antigens                    -> A donates to A, AB
      (B and O recipients have anti-A antibodies).
    - Group B carries B antigens                    -> B donates to B, AB.
    - Group AB carries A and B antigens             -> AB donates to AB only.
  Rh (D antigen):
    - Rh- donors lack the D antigen                 -> Rh- donates to Rh- and Rh+.
    - Rh+ donors carry the D antigen                -> Rh+ donates to Rh+ only
      (Rh- recipients can develop anti-D antibodies).

Consequences: O- is the universal donor, AB+ the universal recipient.
"""

from __future__ import annotations

GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]

# Donor antigens present on red blood cells.
_ABO_ANTIGENS = {"O": frozenset(), "A": frozenset({"A"}),
                 "B": frozenset({"B"}), "AB": frozenset({"A", "B"})}
# Recipient antibodies (plasma) attack antigens the recipient lacks.
_ABO_ANTIBODIES = {"O": frozenset({"A", "B"}), "A": frozenset({"B"}),
                   "B": frozenset({"A"}), "AB": frozenset()}


def parse_group(group: str) -> tuple[str, str]:
    """Split e.g. 'AB-' -> ('AB', '-'). Raises ValueError on bad input."""
    group = group.strip().upper().replace("POS", "+").replace("NEG", "-")
    if group.endswith("+") or group.endswith("-"):
        abo, rh = group[:-1], group[-1]
    else:  # allow bare 'A', 'O', ... -> assume Rh unknown not allowed
        raise ValueError(f"Invalid blood group (missing Rh sign): {group!r}")
    if abo not in _ABO_ANTIGENS:
        raise ValueError(f"Invalid ABO group: {group!r}")
    return abo, rh


def is_compatible(donor_group: str, recipient_group: str) -> bool:
    """True if donor red cells can be transfused to the recipient.

    Medically correct donor->recipient direction (this is NOT symmetric).
    """
    d_abo, d_rh = parse_group(donor_group)
    r_abo, r_rh = parse_group(recipient_group)
    # Recipient antibodies must not attack donor antigens.
    abo_ok = not (_ABO_ANTIGENS[d_abo] & _ABO_ANTIBODIES[r_abo])
    # Rh- recipients must not receive Rh+ blood (anti-D sensitization).
    rh_ok = not (d_rh == "+" and r_rh == "-")
    return abo_ok and rh_ok


def compatibility_matrix() -> dict[str, dict[str, bool]]:
    """Full 8x8 donor(rows) -> recipient(cols) compatibility table."""
    return {d: {r: is_compatible(d, r) for r in GROUPS} for d in GROUPS}


def exactness(donor_group: str, recipient_group: str) -> float:
    """Match quality in [0,1]: exact group > Rh-only difference > cross-group.

    1.0 exact (A+ -> A+); 0.8 ABO same, Rh differs (O- -> O+);
    0.5 compatible across ABO (O+ -> A+); 0.0 incompatible.
    """
    if not is_compatible(donor_group, recipient_group):
        return 0.0
    d_abo, d_rh = parse_group(donor_group)
    r_abo, r_rh = parse_group(recipient_group)
    if d_abo == r_abo and d_rh == r_rh:
        return 1.0
    if d_abo == r_abo:
        return 0.8
    return 0.5


def universal_donors() -> list[str]:
    return [g for g in GROUPS if all(is_compatible(g, r) for r in GROUPS)]


def universal_recipients() -> list[str]:
    return [r for r in GROUPS if all(is_compatible(d, r) for d in GROUPS)]
