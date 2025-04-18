from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import draft_logic

app = FastAPI()

# Allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:5173"] if you want stricter
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize draft
draft_logic.initialize_draft()


@app.get("/draft/state")
def get_draft_state():
    return draft_logic.get_draft_state()

@app.post("/draft/next-pick")
def next_pick():
    draft_logic.auto_pick_next()
    return {"message": "Next pick made"}

@app.post("/draft/pick-player")
def pick_player(payload: dict):
    player_name = payload.get("player_name")
    if not player_name:
        raise HTTPException(status_code=400, detail="Missing player name")
    draft_logic.pick_player(player_name, username="ManualPick")  # simple for now
    return {"message": "Player picked"}

@app.post("/draft/reset")
def reset():
    draft_logic.reset_draft()
    return {"message": "Draft reset"}
