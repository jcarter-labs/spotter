"""POTA API diagnostic tool.

Modes:

  Probe — single fetch, dump raw JSON + observed field names/types:
      python live_pota_test.py --probe

  Live — poll PotaConnection and print spots as they arrive (default):
      python live_pota_test.py
      python live_pota_test.py --center 14025 --bw 50 --duration 120
"""

import argparse
import json
import queue
import signal
import sys
import time

import requests

from cluster import Spot
from pota_client import POTA_URL, PotaConnection

TIMEOUT_S = 10


def mode_probe():
    print(f"GET {POTA_URL} ...")
    try:
        response = requests.get(POTA_URL, timeout=TIMEOUT_S)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)

    print(f"HTTP {response.status_code}")
    response.raise_for_status()

    spots = response.json()
    if not isinstance(spots, list):
        print(f"Unexpected top-level type: {type(spots).__name__} (expected list)")
        print(json.dumps(spots, indent=2)[:2000])
        return

    print(f"Total spots returned: {len(spots)}\n")

    print("=" * 70)
    print("First 3 raw entries:")
    print("=" * 70)
    for spot in spots[:3]:
        print(json.dumps(spot, indent=2))
        print("-" * 40)

    # Union of every key seen across all spots, with one sample value/type
    # each -- catches fields that are only present sometimes.
    field_samples = {}
    for spot in spots:
        if not isinstance(spot, dict):
            continue
        for key, value in spot.items():
            if key not in field_samples:
                field_samples[key] = value

    print("\n" + "=" * 70)
    print(f"Distinct fields observed across all {len(spots)} spots:")
    print("=" * 70)
    for key in sorted(field_samples):
        value = field_samples[key]
        print(f"  {key:<16} {type(value).__name__:<8} sample={value!r}")

    cw_count = sum(
        1 for s in spots
        if isinstance(s, dict) and str(s.get("mode", "")).upper() == "CW"
    )
    print(f"\nCW-mode spots: {cw_count} / {len(spots)}")


def fmt_spot(spot: Spot) -> str:
    return (
        f"{spot.time_utc:<20} {spot.dx_call:<12} {spot.freq_khz:>9.1f} kHz  "
        f"{spot.band:<4}  {spot.mode:<4}  de {spot.spotter:<12}  {spot.comment}"
    )


def mode_live(args):
    window = (args.center, args.bw)
    q = queue.Queue()
    conn = PotaConnection(q, window_fn=lambda: window, poll_seconds=args.poll_seconds)

    lo, hi = args.center - args.bw / 2, args.center + args.bw / 2
    print(f"Polling {POTA_URL} every {args.poll_seconds}s ...")
    print(f"Window: {lo:.1f}-{hi:.1f} kHz, CW only")
    print(f"Running for {args.duration}s — Ctrl+C to stop\n")
    print(f"{'SPOT TIME':<20} {'DX CALL':<12} {'FREQ':>13}  {'BAND':<4}  {'MODE':<4}  {'SPOTTER':<14}  COMMENT")
    print("-" * 100)

    conn.start()

    def shutdown(sig, frame):
        conn.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    count = 0
    deadline = time.monotonic() + args.duration
    while time.monotonic() < deadline:
        try:
            spot = q.get(timeout=0.5)
            count += 1
            print(fmt_spot(spot))
        except queue.Empty:
            pass

    conn.stop()
    print(f"\n{'-' * 100}")
    print(f"Done. Received {count} spots.")


def main():
    parser = argparse.ArgumentParser(description="POTA API diagnostic tool")
    parser.add_argument("--probe", action="store_true",
                        help="Fetch once, dump raw JSON and observed schema")
    parser.add_argument("--center", type=float, default=27000.0,
                        help="Live mode: scope center kHz (default: wide open, all HF+6m bands)")
    parser.add_argument("--bw", type=float, default=100000.0,
                        help="Live mode: scope bandwidth kHz")
    parser.add_argument("--duration", type=int, default=60,
                        help="Live mode: run duration in seconds")
    parser.add_argument("--poll-seconds", type=int, default=60,
                        help="Live mode: poll interval in seconds")
    args = parser.parse_args()

    if args.probe:
        mode_probe()
    else:
        mode_live(args)


if __name__ == "__main__":
    main()
