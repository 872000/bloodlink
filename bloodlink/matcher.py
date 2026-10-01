"""Matching engine: rank compatible + eligible donors per request.

Eligibility: donor must be marked available AND respect the whole-blood
donation cooldown (default 56 days since last donation; never-donated = OK).

Score (per donor for a given request):
    score = 0.50 * compatibility exactness
          + 0.30 * proximity (1 = at the hospital, decaying with distance)
          + 0.20 * urgency weight (urgency / 5)

Requests are processed in urgency order; the global match queue ranks
(request, donor) pairs so critical requests are served first.
"""

from __future__ import annotations

import math
from datetime import date, datetime

from .compatibility import exactness, is_compatible
from . import database as db

COOLDOWN_DAYS = 56  # whole-blood donation interval (Red Cross standard)


def days_since_last_donation(donor, today: date | None = None) -> int | None:
    """Days since last donation; None if the donor has never donated."""
    if not donor["last_donation"]:
        return None
    today = today or date.today()
    last = datetime.strptime(donor["last_donation"], "%Y-%m-%d").date()
    return (today - last).days


def is_eligible(donor, today: date | None = None) -> bool:
    """Available flag + cooldown respected."""
    if not donor["available"]:
        return False
    days = days_since_last_donation(donor, today)
    return days is None or days >= COOLDOWN_DAYS


def distance(ax, ay, bx, by) -> float:
    return math.hypot(ax - bx, ay - by)


def score_donor(donor, request, max_distance: float, today: date | None = None):
    """Return score in [0,1] or None if donor is ineligible/incompatible."""
    if not is_eligible(donor, today):
        return None
    ex = exactness(donor["blood_group"], request["blood_group"])
    if ex == 0.0:
        return None
    dist = distance(donor["x"], donor["y"], request["x"], request["y"])
    proximity = 1.0 - min(dist / max(max_distance, 1e-9), 1.0)
    urgency_w = request["urgency"] / 5.0
    score = 0.50 * ex + 0.30 * proximity + 0.20 * urgency_w
    return round(score, 4)


def match_request(conn, request, today: date | None = None, top_n: int | None = None):
    """Ranked list of (donor_row, score, distance) for one request."""
    donors = db.list_donors(conn)
    dists = [distance(d["x"], d["y"], request["x"], request["y"]) for d in donors]
    max_d = max(dists) if dists else 1.0
    ranked = []
    for donor, dist in zip(donors, dists):
        s = score_donor(donor, request, max_d, today)
        if s is not None:
            ranked.append((donor, s, round(dist, 2)))
    ranked.sort(key=lambda t: (-t[1], t[2]))
    return ranked[:top_n] if top_n else ranked


def global_match_queue(conn, today: date | None = None, per_request: int = 3):
    """(request, donor, score) pairs ordered so urgent requests come first.

    Sort key: urgency desc, then score desc — an urgent request's matches
    always outrank a routine request's matches.
    """
    queue = []
    for req in db.list_requests(conn, only_open=True):
        for donor, score, dist in match_request(conn, req, today, top_n=per_request):
            queue.append((req, donor, score, dist))
    queue.sort(key=lambda t: (-t[0]["urgency"], -t[2]))
    return queue
