"""
Live integration test: connects to DX cluster, prints spots for 60s.
Filtering is server-side via CC Cluster ACCEPT/SPOTS commands.
Usage:
    python live_test.py                        # all spots (CW default)
    python live_test.py --band 20m             # 20m CW only
    python live_test.py --mode CW --dx-continent EU
    python live_test.py --spotter-continent NA
"""

import argparse
import queue
import signal
import sys
import time

from cluster import ClusterConnection, ClusterFilter, Spot
from filters import DedupCache

HOST = "ve7cc.net"
PORT = 23
CALLSIGN = "N6YU"
DURATION = 60


def fmt_spot(spot: Spot) -> str:
    return (
        f"{spot.time_utc}  {spot.dx_call:<12} {spot.freq_khz:>9.1f} kHz  "
        f"{spot.band:<4}  {spot.mode:<7}  "
        f"de {spot.spotter:<12}  "
        f"[{spot.dx_dxcc}/{spot.dx_continent}]  "
        f"{spot.comment}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--band", help="Band filter e.g. 20m (server-side)")
    parser.add_argument("--mode", default="CW", help="Mode filter e.g. CW SSB (server-side, default: CW)")
    parser.add_argument("--spotter-continent", help="Spotter continent e.g. NA (server-side)")
    parser.add_argument("--dx-continent", help="DX continent e.g. EU (server-side)")
    parser.add_argument("--duration", type=int, default=DURATION)
    parser.add_argument("--raw", action="store_true", help="Print raw parsed fields")
    args = parser.parse_args()

    cf = ClusterFilter(
        modes=[args.mode] if args.mode else [],
        bands=[args.band] if args.band else [],
        dx_continents=[args.dx_continent] if args.dx_continent else [],
        spotter_continents=[args.spotter_continent] if args.spotter_continent else [],
    )
    dedup = DedupCache(window_minutes=5)

    q = queue.Queue()
    conn = ClusterConnection(HOST, PORT, CALLSIGN, q, cluster_filter=cf)

    print(f"Connecting to {HOST}:{PORT} as {CALLSIGN} ...")
    active = [f"mode={args.mode}" if args.mode else None,
              f"band={args.band}" if args.band else None,
              f"dx-continent={args.dx_continent}" if args.dx_continent else None,
              f"spotter-continent={args.spotter_continent}" if args.spotter_continent else None]
    active = [x for x in active if x]
    print(f"Server-side filters: {', '.join(active) if active else 'none'}")
    print(f"Running for {args.duration}s — Ctrl+C to stop\n")
    print(f"{'TIME':<6}  {'DX CALL':<12} {'FREQ':>13}  {'BAND':<4}  {'MODE':<7}  {'SPOTTER':<16}  {'DXCC/CONT':<16}  COMMENT")
    print("-" * 110)

    conn.start()

    def shutdown(sig, frame):
        conn.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    count = 0
    shown = 0
    deadline = time.monotonic() + args.duration

    while time.monotonic() < deadline:
        try:
            spot = q.get(timeout=0.5)
            count += 1
            if args.raw:
                print(f"  mode={spot.mode:<8} band={spot.band:<5} dx={spot.dx_call:<12} comment={spot.comment!r}")
                continue
            if dedup.is_dup(spot):
                continue
            dedup.record(spot)
            print(fmt_spot(spot))
            shown += 1
        except queue.Empty:
            pass

    conn.stop()
    print(f"\n{'-' * 110}")
    print(f"Done. Received {count} spots, showed {shown} after dedup.")


if __name__ == "__main__":
    main()
