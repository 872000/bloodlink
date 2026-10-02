"""Real tests for BloodLink.

Compatibility matrix is verified against the medically correct 8x8
donor->recipient table (hardcoded, not derived from the implementation).
"""

from __future__ import annotations

from datetime import date

import pytest

from bloodlink import compatibility as C
from bloodlink import database as db
from bloodlink import demo_data, matcher, notify

TODAY = date(2026, 10, 1)

# Medically correct donor -> recipient table (rows = donors, cols = recipients).
# Derived from transfusion medicine: ABO antibodies + Rh(D) sensitization rules.
EXPECTED = {
    # recipient: O-  O+  A-  A+  B-  B+  AB- AB+
    "O-":  [True, True, True, True, True, True, True, True],
    "O+":  [False, True, False, True, False, True, False, True],
    "A-":  [False, False, True, True, False, False, True, True],
    "A+":  [False, False, False, True, False, False, False, True],
    "B-":  [False, False, False, False, True, True, True, True],
    "B+":  [False, False, False, False, False, True, False, True],
    "AB-": [False, False, False, False, False, False, True, True],
    "AB+": [False, False, False, False, False, False, False, True],
}


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


# ---------- compatibility engine ----------

@pytest.mark.parametrize("donor", C.GROUPS)
@pytest.mark.parametrize("recipient", C.GROUPS)
def test_full_8x8_matrix_against_medical_table(donor, recipient):
    col = C.GROUPS.index(recipient)
    assert C.is_compatible(donor, recipient) is EXPECTED[donor][col], \
        f"{donor} -> {recipient}"


def test_universal_donor_and_recipient():
    assert C.universal_donors() == ["O-"]
    assert C.universal_recipients() == ["AB+"]


def test_rh_rules():
    assert C.is_compatible("O-", "AB+") and not C.is_compatible("AB+", "O-")
    assert not C.is_compatible("O+", "O-")   # Rh+ -> Rh- sensitization risk
    assert C.is_compatible("O-", "O+")         # Rh- -> Rh+ fine
    assert not C.is_compatible("A+", "A-")
    assert C.is_compatible("A-", "A+")


def test_bad_group_raises():
    with pytest.raises(ValueError):
        C.is_compatible("X+", "O-")
    with pytest.raises(ValueError):
        C.is_compatible("A", "O-")


def test_exactness_ordering():
    assert C.exactness("A+", "A+") == 1.0
    assert C.exactness("O-", "O+") == 0.8
    assert C.exactness("O+", "A+") == 0.5
    assert C.exactness("A+", "O-") == 0.0


# ---------- eligibility / cooldown ----------

def _donor(conn, name, group, last=None, avail=True, x=0.0, y=0.0):
    return db.add_donor(conn, name, group, x, y, last, avail)


def test_cooldown_blocks_recent_donor(conn):
    _donor(conn, "Recent", "O-", last="2026-09-20")   # 11 days ago
    _donor(conn, "Eligible", "O-", last="2026-07-15")  # 78 days ago
    _donor(conn, "Newbie", "O-", last=None)            # never donated
    rid = db.add_request(conn, "O-", 1, 3, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    names = [d["name"] for d, _s, _dd in matcher.match_request(conn, req, today=TODAY)]
    assert "Recent" not in names
    assert "Eligible" in names and "Newbie" in names


def test_cooldown_boundary_56_days(conn):
    _donor(conn, "Edge", "A+", last="2026-08-06")  # exactly 56 days before TODAY
    rid = db.add_request(conn, "A+", 1, 3, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    names = [d["name"] for d, _s, _dd in matcher.match_request(conn, req, today=TODAY)]
    assert "Edge" in names


def test_unavailable_flag_blocks(conn):
    _donor(conn, "Busy", "O-", last=None, avail=False)
    rid = db.add_request(conn, "O-", 1, 3, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    assert matcher.match_request(conn, req, today=TODAY) == []


# ---------- matching & scoring ----------

def test_urgent_requests_outrank_non_urgent(conn):
    _donor(conn, "D1", "O-", last=None, x=1.0, y=1.0)
    _donor(conn, "D2", "O-", last=None, x=2.0, y=2.0)
    low = db.add_request(conn, "O-", 1, 1, "Routine Clinic", 0, 0)
    high = db.add_request(conn, "O-", 1, 5, "City ER", 0, 0)
    q = matcher.global_match_queue(conn, today=TODAY, per_request=2)
    urgencies = [req["urgency"] for req, _d, _s, _dd in q]
    assert urgencies == sorted(urgencies, reverse=True)
    assert urgencies[0] == 5 and urgencies[-1] == 1
    first_req_ids = {req["id"] for req, _d, _s, _dd in q[:2]}
    assert first_req_ids == {high}


def test_exact_match_beats_cross_group(conn):
    _donor(conn, "Exact", "A+", last=None, x=5.0, y=5.0)
    _donor(conn, "Cross", "O-", last=None, x=5.0, y=5.0)
    rid = db.add_request(conn, "A+", 1, 3, "Hosp", 5.0, 5.0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    ranked = matcher.match_request(conn, req, today=TODAY)
    assert ranked[0][0]["name"] == "Exact"


def test_closer_donor_ranks_higher(conn):
    _donor(conn, "Near", "O-", last=None, x=0.5, y=0.5)
    _donor(conn, "Far", "O-", last=None, x=50.0, y=50.0)
    rid = db.add_request(conn, "O-", 1, 3, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    ranked = matcher.match_request(conn, req, today=TODAY)
    assert ranked[0][0]["name"] == "Near"


def test_incompatible_donor_excluded(conn):
    _donor(conn, "ABDonor", "AB+", last=None)
    rid = db.add_request(conn, "O-", 1, 3, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    assert matcher.match_request(conn, req, today=TODAY) == []


def test_score_none_for_ineligible(conn):
    _donor(conn, "Recent", "O-", last="2026-09-28")
    donor = conn.execute("SELECT * FROM donors").fetchone()
    rid = db.add_request(conn, "O-", 1, 5, "Hosp", 0, 0)
    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    assert matcher.score_donor(donor, req, 10.0, TODAY) is None


# ---------- notifications ----------

def test_alerts_logged_and_rendered(conn, capsys):
    _donor(conn, "Hero", "O-", last=None)
    rid = db.add_request(conn, "O-", 2, 5, "City ER", 0, 0)
    q = matcher.global_match_queue(conn, today=TODAY, per_request=1)
    msgs = notify.send_alerts(conn, q, channel="sms")
    out = capsys.readouterr().out
    assert len(msgs) == 1
    assert "Hero" in msgs[0] and "City ER" in msgs[0] and "O-" in msgs[0]
    assert "[BloodLink SMS" in out
    logged = conn.execute("SELECT * FROM notifications").fetchall()
    assert len(logged) == 1 and logged[0]["donor_id"] == q[0][1]["id"]


# ---------- drives ----------

def test_drive_schedule_and_list(conn):
    db.schedule_drive(conn, "2026-10-10", "Hall", ["O-", "A+"], 1, 2)
    db.schedule_drive(conn, "2020-01-01", "Old Hall", ["B+"], 0, 0)
    upcoming = db.list_drives(conn, upcoming_only=True)
    assert len(upcoming) == 1 and upcoming[0]["location"] == "Hall"
    assert upcoming[0]["target_groups"] == "O-,A+"
    all_drives = db.list_drives(conn, upcoming_only=False)
    assert len(all_drives) == 2


# ---------- demo data sanity ----------

def test_demo_seed_and_full_pipeline(conn):
    demo_data.seed(conn)
    assert len(db.list_donors(conn)) == 16
    assert len(db.list_requests(conn, only_open=False)) == 5
    q = matcher.global_match_queue(conn, today=TODAY, per_request=3)
    assert q, "demo data should produce matches"
    # critical O- request must be served by O- donors only
    o_neg = [t for t in q if t[0]["blood_group"] == "O-" and t[0]["urgency"] == 5]
    assert o_neg and all(t[1]["blood_group"] == "O-" for t in o_neg)


def test_add_donor_rejects_invalid_blood_group(conn):
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        db.add_donor(conn, "Nobody", "X+", 0, 0)


def test_add_request_rejects_invalid_blood_group(conn):
    with pytest.raises(ValueError, match="[Ii]nvalid"):
        db.add_request(conn, "ZZ", 1, 3, "Hosp", 0, 0)


def test_add_donor_normalizes_group_format(conn):
    did = db.add_donor(conn, "Jane", "a+", 0, 0)
    row = conn.execute("SELECT blood_group FROM donors WHERE id = ?", (did,)).fetchone()
    assert row["blood_group"] == "A+"
