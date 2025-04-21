# backend/main.py

import logging
import traceback
from math import isfinite

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import draft_logic

logger = logging.getLogger(__name__)

class PickRequest(BaseModel):
    player_name: str

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    try:
        draft_logic.initialize_draft()
        logger.info("Draft initialized successfully.")
    except Exception:
        logger.exception("Failed to initialize draft at startup")
        raise  # crash if init fails

@app.get("/draft/state")
def get_state():
    try:
        state = draft_logic.get_draft_state()

        # --- sanitize ADP values ---
        for p in state.get("available_players", []):
            adp = p.get("adp")
            if isinstance(adp, float) and not isfinite(adp):
                p["adp"] = None

        return state
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Error in get_state():\n%s", tb)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/draft/next-pick")
def make_pick():
    try:
        draft_logic.auto_pick_best()
        return {"message": "Auto-picked best player"}
    except Exception as e:
        logger.exception("Error in make_pick()")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/draft/pick-player")
def pick_player(req: PickRequest):
    try:
        draft_logic.pick_player(req.player_name)
        return {"message": f"Picked {req.player_name}"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error in pick_player()")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/draft/reset")
def reset():
    try:
        draft_logic.reset_draft()
        return {"message": "Draft reset"}
    except Exception as e:
        logger.exception("Error in reset()")
        raise HTTPException(status_code=500, detail=str(e))