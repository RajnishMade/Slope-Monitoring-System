"""
serial_bridge.py  —  USB-Serial path for the LoRa receiver.

Use this on the laptop when the receiver forwards packets over USB Serial
instead of Wi-Fi. It reads one JSON packet per line from the receiver's
serial port and POSTs each to the FastAPI server.

Install once:   pip install pyserial requests
Run:            python3 Firmware/serial_bridge.py --port /dev/tty.usbserial-0001
                python3 Firmware/serial_bridge.py --port COM5 --baud 115200

Find the port:  macOS/Linux ->  ls /dev/tty.*     Windows ->  Device Manager
"""

import argparse
import json

import requests
import serial  # pip install pyserial


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="serial device, e.g. /dev/tty.usbserial-0001 or COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--url", default="http://127.0.0.1:8000/api/ingest")
    args = ap.parse_args()

    print(f"Reading {args.port} @ {args.baud}  ->  {args.url}  (Ctrl-C to stop)")
    ser = serial.Serial(args.port, args.baud, timeout=2)

    while True:
        raw = ser.readline().decode("utf-8", "ignore").strip()
        if not raw:
            continue
        try:
            packet = json.loads(raw)          # only forward valid JSON packets
        except json.JSONDecodeError:
            continue                          # ignore boot logs / TX echoes
        if "slope_id" not in packet:
            continue
        try:
            r = requests.post(args.url, json=packet, timeout=10)
            d = r.json()
            print(f"  {packet['slope_id']:10s} -> FoS={d.get('fos')}  {d.get('status')}")
        except Exception as e:
            print(f"  POST failed: {e}")


if __name__ == "__main__":
    main()
