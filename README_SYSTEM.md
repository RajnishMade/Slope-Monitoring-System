# Slope Stability Platform

A real-time slope-stability monitoring and Factor-of-Safety (FoS) prediction
platform built around the existing **TabPFN planar-failure regressor** (the
trained model and its `predict()` are used unchanged).

Two workflows share one model:

```
                         SLOPE STABILITY SYSTEM
                                  │
                ┌─────────────────┴──────────────────┐
        CURRENT SLOPE STATUS                 REAL-TIME MONITORING
        (manual / static)                    (dynamic / continuous)
                │                                     │
        enter 9 model features               select a saved Slope ID
                │                                     │
          existing ML model                  ESP32 sensor data (API)
                │                                     │
           current FoS                        map sensors → model features
                │                                     │
        set FoS threshold                     existing ML model → FoS
                │                                     │
        generate Slope ID  ───────saved──────►  FoS-vs-Time graph
                                                      │
                                              compare with threshold
                                                 ┌────┴────┐
                                              normal     ALERT → notify
```

## The two workflows

**Current Slope Status** — the user manually enters the exact parameters the
model requires, gets an instant FoS + stability status, sets a per-slope FoS
**alert threshold**, and saves it under an auto-generated **Slope ID**
(`SLOPE-001`, `SLOPE-002`, …).

**Real-Time Monitoring** — the user picks a saved Slope ID. Its static
parameters are loaded, and live sensor data (from an ESP32, or the simulator)
updates the dynamic inputs. Each reading is scored by the same model and
appended to a **FoS-vs-Time** graph. When FoS reaches/crosses the slope's
threshold, the dashboard raises a clear alert.

## Model inputs vs. sensors (important, and honest)

The trained model takes **9 features**. In monitoring, only the two that
correspond to real sensors are updated live; the rest are the slope's stored
survey values. No model input is invented or removed.

| Sensor (ESP32) | → model feature | Role |
|----------------|-----------------|------|
| water / pore-water (0–1) | `water_level` | **model input** |
| vibration / ground accel (g) | `seismic_kh` | **model input** |
| tilt / inclination (°) | — | telemetry only |
| displacement (mm) | — | telemetry only |
| crack width (mm) | — | telemetry only |

Tilt, displacement and crack are displayed as live telemetry but do **not**
feed the model (it was not trained on them). Alerting is purely FoS-vs-threshold.

## Status logic (per slope, relative to its threshold)

| Status | Condition |
|--------|-----------|
| STABLE  | FoS > threshold × 1.10 |
| WARNING | threshold < FoS ≤ threshold × 1.10 (approaching) |
| ALERT   | FoS ≤ threshold (alert generated) |

## What's here

```
Server/
  main.py            FastAPI: /api/predict, /api/slopes (CRUD), /api/ingest, /api/meta
  scorer.py          TabPFN wrapper — UNCHANGED model, fit once, predict per call
  db.py              SQLite: slopes + readings (source-tagged)
  config_server.py   threshold-relative status logic
  simulate.py        CLI sensor simulator (source="simulated")
  templates/index.html, static/{app.js,styles.css}   glassmorphism SPA
Firmware/
  sensor_node/sensor_node.ino      ESP32 sensor node (LoRa TX)
  lora_receiver/lora_receiver.ino  ESP32 receiver → Wi-Fi POST /api/ingest
  serial_bridge.py                 laptop-side USB-serial → server
PlaneFailure/planeTabpfnReport.py  offline model metrics
Src/, Data/, Models/               the trained plane-failure model + data
```

## Run it (no hardware)

```bash
cd "IIT Bombay"
pip install -r requirements.txt
cd Server && uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. A demo slope (`SLOPE-001`) is seeded so
Real-Time Monitoring works immediately. Drive it two ways:

- **In the dashboard:** open Real-Time Monitoring → **Start simulated feed**
  (clearly labelled "Simulated (mock)").
- **From the CLI:** `python3 Server/simulate.py --slope SLOPE-001`

Both send `source="simulated"`, kept visually distinct from real `esp32` data.

## ESP32 integration (real hardware)

The ESP32 posts JSON to the ingest API — HTTP directly, or over LoRa to a
receiver that forwards it:

```
POST /api/ingest
{ "slope_id": "SLOPE-001", "source": "esp32",
  "water": 0.32, "vibration": 0.04, "tilt": 2.1, "displacement": 6.3, "crack": 0.8 }
```

1. Flash `Firmware/sensor_node/sensor_node.ino`; set `SLOPE_ID` to a slope that
   exists in the app, plus LoRa pins/frequency and sensor calibration.
2. Flash `Firmware/lora_receiver/lora_receiver.ino`; set Wi-Fi + `SERVER_URL`
   (`http://<laptop-ip>:8000/api/ingest`).
   *USB alt:* `python3 Firmware/serial_bridge.py --port <serial-port>`.

Readings tagged `source="esp32"` show as **ESP32 (hardware)** with a green
Connected indicator; simulated data shows amber **Simulated (mock)**.

## HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/predict` | `{params}` → FoS (stateless preview) |
| POST | `/api/slopes` | `{name?, params, threshold}` → create slope, returns Slope ID |
| GET | `/api/slopes` | list slopes + latest status |
| GET | `/api/slopes/{id}` | one slope + latest reading |
| DELETE | `/api/slopes/{id}` | delete slope + its history |
| POST | `/api/ingest` | `{slope_id, source, water, vibration, tilt, displacement, crack}` → FoS + alert |
| GET | `/api/slopes/{id}/readings?limit=` | FoS-vs-time history (rolling window) |
| GET | `/api/meta` | model features, sensor defs, status colors |

## Model accuracy

5-fold CV on the 149-slope dataset (`PlaneFailure/planeTabpfnReport.py`):
**R² 0.965 · MAE 0.063 · RMSE 0.166 · MAPE 7.35%**, 94.0% stable/unstable
accuracy at the FoS = 1.0 boundary. The model is not modified by this platform.
```
Server/monitoring.db (SQLite) is created on first run; delete it to reset.
```
