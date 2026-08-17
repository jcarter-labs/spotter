"""POTA API diagnostic tool.

Step 1 of Stage 4 (see spotter_master_plan.md): confirm the real shape of
https://api.pota.app/spot/activator before writing the Spot normalizer.

Modes:

  Probe — single fetch, dump raw JSON + observed field names/types:
      python live_pota_test.py --probe

  (Live polling smoke test mode arrives in Stage 4E, once the normalizer
  and PotaConnection worker exist.)
"""

import argparse
import json
import sys

import requests

POTA_URL = "https://api.pota.app/spot/activator"
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


def main():
    parser = argparse.ArgumentParser(description="POTA API diagnostic tool")
    parser.add_argument("--probe", action="store_true",
                        help="Fetch once, dump raw JSON and observed schema")
    args = parser.parse_args()

    if args.probe:
        mode_probe()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
