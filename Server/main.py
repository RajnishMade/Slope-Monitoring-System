"""
main.py
FastAPI backend for the Slope Stability platform.

Two workflows, one shared (unchanged) TabPFN model:

  OPTION 1 — Current Slope Status  (manual / static)
      user enters the 9 model features -> POST /api/predict  -> FoS
      user sets an alert threshold      -> POST /api/slopes   -> Slope ID saved

  OPTION 2 — Real-Time Monitoring   (dynamic / continuous)
      ESP32 (or simulator) posts sensor data -> POST /api/ingest
      backend maps sensors -> the SAME model -> FoS -> threshold check -> alert
      dashboard polls /api/slopes/{id}/readings for the FoS-vs-time graph

Dynamic model inputs come only from sensors that map to real model features:
    water sensor      -> water_level   (saturation, 0-1)
    vibration sensor  -> seismic_kh    (pseudo-static seismic coefficient)
Tilt / displacement / crack are shown as telemetry but are NOT model inputs
(the trained model does not take them). No model input is invented or removed.

Run:  cd Server && uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import db
import config_server as cfg
from scorer import FosScorer

STATE: dict = {"scorer": None}

# ---- model feature metadata (labels/units/ranges for the manual form) -------
# Keyed by the EXACT model feature name; order is taken from the model itself.
FEATURE_META = {
    "slope_angle_af_deg":       {"label": "Slope face angle (ψf)",      "unit": "°",      "min": 0,  "max": 90,  "step": 1,    "default": 45,   "dynamic": False},
    "failure_plane_dip_ap_deg": {"label": "Failure plane dip (ψp)",     "unit": "°",      "min": 0,  "max": 90,  "step": 1,    "default": 35,   "dynamic": False},
    "upper_slope_angle_as_deg": {"label": "Upper slope angle (ψs)",     "unit": "°",      "min": 0,  "max": 90,  "step": 1,    "default": 10,   "dynamic": False},
    "h_m":                      {"label": "Slope height (H)",           "unit": "m",      "min": 1,  "max": 500, "step": 1,    "default": 60,   "dynamic": False},
    "unit_weight_gamma_kNm3":   {"label": "Unit weight (γ)",            "unit": "kN/m³",  "min": 15, "max": 32,  "step": 0.1,  "default": 25,   "dynamic": False},
    "friction_angle_phi_deg":   {"label": "Friction angle (φ)",         "unit": "°",      "min": 0,  "max": 60,  "step": 0.5,  "default": 35,   "dynamic": False},
    "cohesion_C_kPa":           {"label": "Cohesion (c)",               "unit": "kPa",    "min": 0,  "max": 500, "step": 1,    "default": 80,   "dynamic": False},
    "seismic_kh":               {"label": "Seismic coefficient (kₕ)",   "unit": "",       "min": 0,  "max": 0.5, "step": 0.01, "default": 0.0,  "dynamic": True, "sensor": "vibration"},
    "water_level":              {"label": "Water level / saturation",   "unit": "0–1",    "min": 0,  "max": 1,   "step": 0.01, "default": 0.1,  "dynamic": True, "sensor": "water"},
}

# ---- ESP32 sensor definitions (monitoring) ----------------------------------
SENSORS = [
    {"key": "water",        "label": "Water level / saturation", "unit": "0–1", "maps_to": "water_level", "model_input": True},
    {"key": "vibration",    "label": "Vibration / ground accel", "unit": "g",   "maps_to": "seismic_kh",  "model_input": True},
    {"key": "tilt",         "label": "Tilt / inclination",       "unit": "°",   "maps_to": None,          "model_input": False},
    {"key": "displacement", "label": "Displacement",             "unit": "mm",  "maps_to": None,          "model_input": False},
    {"key": "crack",        "label": "Crack width",              "unit": "mm",  "maps_to": None,          "model_input": False},
]
KH_MAX = 0.5


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def seed_demo_slope():
    """Create one demo slope so Real-Time Monitoring works out-of-the-box."""
    if db.list_slopes():
        return
    scorer = STATE["scorer"]
    # A realistic, water-sensitive slope: comfortably stable when dry, but the
    # FoS drops below the threshold as saturation rises (so monitoring shows a
    # full STABLE -> WARNING -> ALERT -> recover cycle).
    params = {
        "slope_angle_af_deg": 50, "failure_plane_dip_ap_deg": 42,
        "upper_slope_angle_as_deg": 10, "h_m": 150, "unit_weight_gamma_kNm3": 26.98,
        "friction_angle_phi_deg": 40.0, "cohesion_C_kPa": 156.96,
        "seismic_kh": 0.0, "water_level": 0.05,
    }
    fos = scorer.predict_fos(params)
    threshold = 1.00
    sid = db.next_slope_id()
    db.create_slope({"slope_id": sid, "name": "Demo — East Face (Km 42)",
                     "params": params, "baseline_fos": fos, "threshold": threshold})
    status, alert = cfg.classify(fos, threshold)
    db.insert_reading({"slope_id": sid, "ts": db.now_iso(), "source": "manual",
                       "sensors": {}, "water_level": params["water_level"],
                       "seismic_kh": params["seismic_kh"], "fos": round(fos, 4),
                       "status": status, "alert": int(alert)})
    print(f"[seed] demo slope {sid}  baseline FoS={fos:.3f}  threshold={threshold}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    STATE["scorer"] = FosScorer().load()
    print(f"[startup] TabPFN fitted on {STATE['scorer'].n_train} rows")
    seed_demo_slope()
    yield


app = FastAPI(title="Slope Stability Platform", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


# ------------------------------ schemas ------------------------------

class PredictReq(BaseModel):
    params: dict
    threshold: Optional[float] = None


class CreateSlopeReq(BaseModel):
    name: Optional[str] = None
    params: dict
    threshold: float = Field(gt=0)


class IngestReq(BaseModel):
    slope_id: str
    source: str = "esp32"                 # esp32 | simulated
    water: Optional[float] = None
    vibration: Optional[float] = None
    tilt: Optional[float] = None
    displacement: Optional[float] = None
    crack: Optional[float] = None


def validate_params(params: dict) -> dict:
    feats = STATE["scorer"].features
    out = {}
    for f in feats:
        if f not in params or params[f] is None:
            raise HTTPException(422, f"Missing model feature: {f}")
        try:
            out[f] = float(params[f])
        except (TypeError, ValueError):
            raise HTTPException(422, f"Feature {f} must be numeric")
    return out


def slope_view(slope: dict) -> dict:
    latest = db.latest_reading(slope["slope_id"])
    if latest:
        status, cur = latest["status"], latest["fos"]
    else:
        cur = slope["baseline_fos"]
        status = cfg.classify(cur, slope["threshold"])[0]
    return {**slope, "latest": latest, "current_fos": cur, "status": status}


# ------------------------------- pages -------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health():
    return {"ok": STATE["scorer"] is not None, "slopes": len(db.list_slopes())}


@app.get("/api/meta")
def meta():
    scorer = STATE["scorer"]
    features = [{"key": k, **FEATURE_META[k]} for k in scorer.features]
    return {"features": features, "sensors": SENSORS, "status": cfg.meta(), "model": scorer.meta()}


# ---------------------- option 1: current status ---------------------

@app.post("/api/predict")
def predict(req: PredictReq):
    feats = validate_params(req.params)
    fos = STATE["scorer"].predict_fos(feats)
    out = {"fos": round(fos, 4)}
    if req.threshold is not None:
        status, alert = cfg.classify(fos, req.threshold)
        out.update(status=status, alert=alert, threshold=req.threshold)
    return out


@app.post("/api/slopes")
def create_slope(req: CreateSlopeReq):
    feats = validate_params(req.params)
    fos = STATE["scorer"].predict_fos(feats)
    sid = db.next_slope_id()
    db.create_slope({"slope_id": sid, "name": req.name, "params": feats,
                     "baseline_fos": round(fos, 4), "threshold": req.threshold})
    status, alert = cfg.classify(fos, req.threshold)
    db.insert_reading({"slope_id": sid, "ts": db.now_iso(), "source": "manual",
                       "sensors": {}, "water_level": feats["water_level"],
                       "seismic_kh": feats["seismic_kh"], "fos": round(fos, 4),
                       "status": status, "alert": int(alert)})
    return slope_view(db.get_slope(sid))


@app.get("/api/slopes")
def slopes():
    return {"slopes": [slope_view(s) for s in db.list_slopes()]}


@app.get("/api/slopes/{slope_id}")
def slope_detail(slope_id: str):
    s = db.get_slope(slope_id)
    if not s:
        raise HTTPException(404, f"Unknown slope '{slope_id}'")
    return slope_view(s)


@app.delete("/api/slopes/{slope_id}")
def remove_slope(slope_id: str):
    if not db.get_slope(slope_id):
        raise HTTPException(404, f"Unknown slope '{slope_id}'")
    db.delete_slope(slope_id)
    return {"deleted": slope_id}


# ---------------------- option 2: monitoring -------------------------

@app.post("/api/ingest")
def ingest(req: IngestReq):
    slope = db.get_slope(req.slope_id)
    if not slope:
        raise HTTPException(404, f"Unknown slope '{req.slope_id}' (create it in Current Slope Status)")

    feats = dict(slope["params"])
    if req.water is not None:
        feats["water_level"] = clamp(req.water, 0, 1)
    if req.vibration is not None:
        feats["seismic_kh"] = clamp(req.vibration, 0, KH_MAX)

    fos = STATE["scorer"].predict_fos(feats)
    status, alert = cfg.classify(fos, slope["threshold"])

    sensors = {k: getattr(req, k) for k in ("water", "vibration", "tilt", "displacement", "crack")
               if getattr(req, k) is not None}
    row = {"slope_id": req.slope_id, "ts": db.now_iso(), "source": req.source,
           "sensors": sensors, "water_level": round(feats["water_level"], 4),
           "seismic_kh": round(feats["seismic_kh"], 4), "fos": round(fos, 4),
           "status": status, "alert": int(alert)}
    row["id"] = db.insert_reading(row)
    row["threshold"] = slope["threshold"]
    return row


@app.get("/api/slopes/{slope_id}/readings")
def slope_readings(slope_id: str, limit: int = 120):
    slope = db.get_slope(slope_id)
    if not slope:
        raise HTTPException(404, f"Unknown slope '{slope_id}'")
    return {"slope_id": slope_id, "threshold": slope["threshold"],
            "baseline_fos": slope["baseline_fos"], "name": slope["name"],
            "readings": db.recent_readings(slope_id, limit)}
