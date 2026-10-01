"""BloodLink CLI: registry, matching, alerts, drives, charts, demo."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import database as db
from . import demo_data, matcher, notify, visuals
from .compatibility import GROUPS, is_compatible, compatibility_matrix

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def _conn(args):
    return db.connect(args.db)


def cmd_seed(args):
    conn = _conn(args)
    demo_data.seed(conn)
    n_d = len(db.list_donors(conn))
    n_r = len(db.list_requests(conn, only_open=False))
    print(f"Seeded demo data: {n_d} donors, {n_r} requests, "
          f"{len(db.list_drives(conn, upcoming_only=False))} drives -> {args.db}")


def cmd_donors(args):
    conn = _conn(args)
    for d in db.list_donors(conn):
        elig = "eligible" if matcher.is_eligible(d) else "INELIGIBLE"
        print(f"#{d['id']:>2} {d['name']:<16} {d['blood_group']:<4} "
              f"({d['x']},{d['y']}) last={d['last_donation'] or 'never':<10} "
              f"{'avail' if d['available'] else 'UNAVAIL':<7} {elig}")


def cmd_requests(args):
    conn = _conn(args)
    for r in db.list_requests(conn, only_open=False):
        print(f"#{r['id']:>2} needs {r['units']}u {r['blood_group']:<4} "
              f"urgency={r['urgency']}/5 @ {r['hospital']} ({r['x']},{r['y']}) [{r['status']}]")


def cmd_match(args):
    conn = _conn(args)
    today = date.fromisoformat(args.today) if args.today else date.today()
    queue = matcher.global_match_queue(conn, today=today, per_request=args.per_request)
    if not queue:
        print("No matches found.")
        return
    current_req = None
    for req, donor, score, dist in queue:
        if req["id"] != current_req:
            current_req = req["id"]
            print(f"\n[Request #{req['id']}] {req['units']}u {req['blood_group']} "
                  f"urgency={req['urgency']}/5 @ {req['hospital']}")
        print(f"   {score:.3f}  {donor['name']:<16} {donor['blood_group']:<4} "
              f"dist={dist:.1f}")
    print(f"\n{len(queue)} matches across {len({q[0]['id'] for q in queue})} requests.")


def cmd_notify(args):
    conn = _conn(args)
    today = date.fromisoformat(args.today) if args.today else date.today()
    queue = matcher.global_match_queue(conn, today=today, per_request=args.per_request)
    msgs = notify.send_alerts(conn, queue, channel=args.channel)
    print(f"\n{len(msgs)} alert(s) simulated via '{args.channel}' and logged.")


def cmd_drives(args):
    conn = _conn(args)
    if args.schedule:
        d, loc, groups = args.schedule
        x = float(args.x or 0)
        y = float(args.y or 0)
        did = db.schedule_drive(conn, d, loc, [g for g in groups.split(",")], x, y)
        print(f"Scheduled drive #{did}: {d} @ {loc} targeting [{groups}]")
        return
    drives = db.list_drives(conn, upcoming_only=not args.all)
    if not drives:
        print("No drives found.")
        return
    for dr in drives:
        print(f"#{dr['id']:>2} {dr['date']}  {dr['location']:<28} "
              f"targets: {dr['target_groups']}")


def cmd_add_donor(args):
    conn = _conn(args)
    did = db.add_donor(conn, args.name, args.group.upper(), args.x, args.y,
                       args.last_donation, not args.unavailable)
    print(f"Added donor #{did}: {args.name} ({args.group.upper()})")


def cmd_add_request(args):
    conn = _conn(args)
    rid = db.add_request(conn, args.group.upper(), args.units, args.urgency,
                         args.hospital, args.x, args.y)
    print(f"Added request #{rid}: {args.units}u {args.group.upper()} "
          f"urgency={args.urgency}/5 @ {args.hospital}")


def cmd_compat(args):
    if args.donor and args.recipient:
        ok = is_compatible(args.donor.upper(), args.recipient.upper())
        print(f"{args.donor.upper()} -> {args.recipient.upper()}: "
              f"{'COMPATIBLE' if ok else 'NOT compatible'}")
        return
    m = compatibility_matrix()
    print("      " + " ".join(f"{g:>4}" for g in GROUPS) + "   <- recipient")
    for d in GROUPS:
        print(f"{d:>4}  " + " ".join("  ✓ " if m[d][r] else "  ✗ " for r in GROUPS))


def cmd_chart(args):
    conn = _conn(args)
    today = date.fromisoformat(args.today) if args.today else date.today()
    ASSETS.mkdir(exist_ok=True)
    hm = visuals.compatibility_heatmap(str(ASSETS / "compatibility_heatmap.png"))
    print(f"Wrote {hm}")
    queue = matcher.global_match_queue(conn, today=today, per_request=3)
    mc = visuals.match_chart(queue, str(ASSETS / "match_results.png"))
    print(f"Wrote {mc}")


def cmd_demo(args):
    """Full out-of-the-box demo: seed -> match -> alerts -> charts."""
    import os, tempfile
    demo_db = ROOT / "bloodlink.db"
    if demo_db.exists():
        demo_db.unlink()
    args.db = str(demo_db)
    cmd_seed(args)
    print("\n=== COMPATIBILITY MATRIX ===")
    cmd_compat(argparse.Namespace(donor=None, recipient=None))
    print("\n=== MATCHING (urgency-weighted) ===")
    cmd_match(args)
    print("\n=== SIMULATED DONOR ALERTS ===")
    cmd_notify(args)
    print("\n=== UPCOMING BLOOD DRIVES ===")
    cmd_drives(argparse.Namespace(db=args.db, schedule=None, all=False, x=None, y=None))
    print("\n=== CHARTS ===")
    cmd_chart(args)
    print("\nDemo complete. Charts in assets/.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bloodlink",
                                description="BloodLink — blood donor <-> request matcher (UN SDG 3)")
    p.add_argument("--db", default=str(ROOT / "bloodlink.db"), help="SQLite db path")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("seed", help="Load bundled demo donors/requests/drives")
    s.set_defaults(func=cmd_seed)

    s = sub.add_parser("donors", help="List donor registry")
    s.set_defaults(func=cmd_donors)

    s = sub.add_parser("requests", help="List blood requests")
    s.set_defaults(func=cmd_requests)

    s = sub.add_parser("match", help="Rank compatible donors per request")
    s.add_argument("--per-request", type=int, default=3)
    s.add_argument("--today", default=None, help="YYYY-MM-DD (default: today)")
    s.set_defaults(func=cmd_match)

    s = sub.add_parser("notify", help="Simulate SMS/console alerts to matched donors")
    s.add_argument("--per-request", type=int, default=3)
    s.add_argument("--channel", default="sms", choices=["sms", "console"])
    s.add_argument("--today", default=None)
    s.set_defaults(func=cmd_notify)

    s = sub.add_parser("drives", help="List or schedule blood drives")
    s.add_argument("--schedule", nargs=3, metavar=("DATE", "LOCATION", "GROUPS"),
                   help="Schedule a drive; GROUPS comma-separated, e.g. 'O-,O+,B-'")
    s.add_argument("--x", default=None); s.add_argument("--y", default=None)
    s.add_argument("--all", action="store_true", help="Include past drives")
    s.set_defaults(func=cmd_drives)

    s = sub.add_parser("add-donor", help="Register a donor")
    s.add_argument("name"); s.add_argument("group")
    s.add_argument("--x", type=float, default=0.0); s.add_argument("--y", type=float, default=0.0)
    s.add_argument("--last-donation", default=None)
    s.add_argument("--unavailable", action="store_true")
    s.set_defaults(func=cmd_add_donor)

    s = sub.add_parser("add-request", help="Register a blood request")
    s.add_argument("group"); s.add_argument("units", type=int)
    s.add_argument("urgency", type=int); s.add_argument("hospital")
    s.add_argument("--x", type=float, default=0.0); s.add_argument("--y", type=float, default=0.0)
    s.set_defaults(func=cmd_add_request)

    s = sub.add_parser("compat", help="Check ABO/Rh compatibility")
    s.add_argument("--donor", default=None); s.add_argument("--recipient", default=None)
    s.set_defaults(func=cmd_compat)

    s = sub.add_parser("chart", help="Generate compatibility heatmap + match chart")
    s.add_argument("--today", default=None)
    s.set_defaults(func=cmd_chart)

    s = sub.add_parser("demo", help="Run the full bundled demo")
    s.add_argument("--today", default="2026-10-01")
    s.add_argument("--per-request", type=int, default=3)
    s.add_argument("--channel", default="sms")
    s.set_defaults(func=cmd_demo)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
