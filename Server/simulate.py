"""
simulate.py
Hardware-free sensor simulator (server-side / CLI). Stands in for the ESP32 +
LoRa receiver by POSTing sensor packets to /api/ingest for an existing Slope ID,
with source="simulated" so the data is clearly separated from real hardware.

It drives a rainfall cycle: water (and vibration) rise then fall, so the FoS
crosses the slope's threshold (ALERT) and recovers — exactly what the dashboard
FoS-vs-Time graph and alert system are meant to show.

Usage:
    python3 Server/simulate.py                       # slope = SLOPE-001
    python3 Server/simulate.py --slope SLOPE-002 --interval 1
    python3 Server/simulate.py --url http://192.168.1.50:8000
"""

import argparse
import math
import random
import time

import requests


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--slope", default=None, help="Slope ID (default: first slope on the server)")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--steps", type=int, default=0, help="0 = run until Ctrl-C")
    ap.add_argument("--period", type=int, default=60, help="steps per rainfall cycle")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    slopes = requests.get(f"{base}/api/slopes", timeout=10).json()["slopes"]
    if not slopes:
        raise SystemExit("No slopes on the server. Create one in 'Current Slope Status' first.")
    slope_id = args.slope or slopes[0]["slope_id"]
    thr = next((s["threshold"] for s in slopes if s["slope_id"] == slope_id), None)
    if thr is None:
        raise SystemExit(f"Slope {slope_id} not found.")
    print(f"Simulating {slope_id} (threshold {thr}) -> {base}  [source=simulated]  Ctrl-C to stop")

    step = 0
    while args.steps == 0 or step < args.steps:
        cyc = (1 - math.cos((step % args.period) / args.period * 2 * math.pi)) / 2  # 0..1..0
        j = lambda a: a * (random.random() - 0.5)
        payload = {
            "slope_id": slope_id, "source": "simulated",
            "water": round(clamp(0.03 + 0.72 * cyc + j(0.03), 0, 1), 3),
            "vibration": round(clamp(0.004 + 0.10 * cyc + j(0.015), 0, 0.4), 3),
            "tilt": round(max(0, 0.3 + 4 * cyc + j(0.6)), 2),
            "displacement": round(max(0, 1 + 18 * cyc + j(2)), 2),
            "crack": round(max(0, 0.2 + 3 * cyc + j(0.4)), 2),
        }
        try:
            d = requests.post(f"{base}/api/ingest", json=payload, timeout=10).json()
            flag = "  <== ALERT" if d.get("alert") else ""
            print(f"  water={payload['water']:.2f} vib={payload['vibration']:.2f} "
                  f"-> FoS={d['fos']:.3f}  {d['status']}{flag}")
        except Exception as e:
            print(f"  POST failed: {e}")
        step += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
