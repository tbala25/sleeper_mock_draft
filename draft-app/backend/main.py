from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from draft_logic import DraftManager
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Only allow frontend dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


draft = DraftManager()

class PlayerPick(BaseModel):
    player_name: str

@app.get("/draft/state")
def get_draft_state():
    return draft.get_current_state()

@app.post("/draft/next-pick")
def make_next_pick():
    return draft.make_next_pick()

@app.post("/draft/pick-player")
def pick_specific_player(pick: PlayerPick):
    return draft.pick_specific_player(pick.player_name)

@app.post("/draft/reset")
def reset_draft():
    draft.reset()
    return {"status": "reset done"}
