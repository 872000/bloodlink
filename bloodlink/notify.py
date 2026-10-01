"""Simulated donor notifications (console + SMS-style)."""

from __future__ import annotations

from . import database as db

CHANNELS = ("console", "sms")


def render_sms(donor, request, score) -> str:
    return (
        f"[BloodLink SMS -> {donor['name']}] URGENT: {request['hospital']} needs "
        f"{request['units']} unit(s) of {request['blood_group']} blood "
        f"(urgency {request['urgency']}/5). You ({donor['blood_group']}) are a "
        f"match (score {score:.2f}). Reply YES to confirm donation."
    )


def send_alerts(conn, matches, channel: str = "sms", dry_run_print: bool = True):
    """matches: iterable of (request, donor, score, distance).

    Prints simulated alerts and logs them to the notifications table.
    Returns the list of rendered messages.
    """
    if channel not in CHANNELS:
        raise ValueError(f"channel must be one of {CHANNELS}")
    sent = []
    for request, donor, score, _dist in matches:
        msg = render_sms(donor, request, score)
        sent.append(msg)
        db.log_notification(conn, donor["id"], request["id"], channel, msg)
        if dry_run_print:
            print(msg)
    return sent
