"""Bundled demo data: 16 donors, 5 requests, 3 blood drives.

Coordinates are abstract map units (x, y); last_donation dates are relative
to 2026-10-01 so the demo is deterministic (pass today=date(2026,10,1)).
"""

from __future__ import annotations

DONORS = [
    # name, group, x, y, last_donation, available
    ("Aarav Sharma", "O-", 2.0, 3.0, "2026-07-15", True),   # 78d ago -> eligible
    ("Maya Chen", "A+", 5.0, 5.0, "2026-09-20", True),       # 11d ago -> cooldown
    ("Liam O'Brien", "O+", 4.0, 6.0, "2026-06-01", True),   # eligible
    ("Sofia Rossi", "B-", 8.0, 2.0, None, True),             # never donated
    ("Noah Kim", "AB+", 7.0, 7.0, "2026-08-01", True),      # 61d -> eligible
    ("Priya Nair", "A-", 3.0, 8.0, "2026-05-10", True),      # eligible
    ("Lucas Silva", "B+", 9.0, 9.0, "2026-09-25", True),    # 6d -> cooldown
    ("Emma Wilson", "O-", 1.0, 1.0, "2026-08-10", True),     # 52d -> cooldown
    ("Arjun Patel", "AB-", 6.0, 3.0, "2026-04-20", True),   # eligible
    ("Olivia Brown", "A+", 5.5, 4.5, "2026-03-15", False),  # unavailable
    ("Ethan Davis", "O+", 2.5, 7.5, "2026-07-01", True),    # 92d -> eligible
    ("Ava Garcia", "B+", 8.5, 5.5, None, True),             # never donated
    ("Kabir Singh", "O-", 3.5, 2.5, "2026-01-05", True),    # eligible
    ("Zoe Martin", "A-", 4.5, 9.0, "2026-08-20", True),     # 42d -> cooldown
    ("Ravi Kumar", "B-", 7.5, 1.5, "2026-06-15", True),     # eligible
    ("Nina Petrova", "AB+", 9.5, 3.5, "2026-09-28", True),  # 3d -> cooldown
]

REQUESTS = [
    # group, units, urgency, hospital, x, y
    ("O-", 3, 5, "City General ER", 3.0, 4.0),        # critical, rare group
    ("A+", 2, 4, "St. Mary's Hospital", 5.0, 5.0),    # high urgency
    ("B+", 1, 2, "Riverside Clinic", 8.0, 6.0),       # routine
    ("AB-", 2, 5, "City General ER", 3.0, 4.0),       # critical
    ("O+", 4, 3, "Northside Medical", 2.0, 7.0),      # medium
]

DRIVES = [
    # date, location, target groups, x, y
    ("2026-10-10", "Central Community Hall", ["O-", "O+", "B-"], 4.0, 4.0),
    ("2026-10-17", "University Campus Center", ["A+", "AB+", "B+"], 6.0, 6.0),
    ("2026-10-24", "Riverside Mall Atrium", ["A-", "AB-", "O-"], 8.0, 3.0),
]


def seed(conn):
    from . import database as db
    for row in DONORS:
        db.add_donor(conn, *row)
    for row in REQUESTS:
        db.add_request(conn, *row)
    for date_, loc, targets, x, y in DRIVES:
        db.schedule_drive(conn, date_, loc, targets, x, y)
