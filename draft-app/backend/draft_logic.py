# backend/draft_logic.py

import requests
import pandas as pd
import requests_cache
import warnings
from math import isfinite

warnings.filterwarnings("ignore")
requests_cache.install_cache('sleeper', expire_after=43200)

# --- CONFIG ---
league_id        = "1180634108313018368"
csv_file_path    = "./FantasyPros_2025_Dynasty_OP_Rankings.csv"

starter_quality_counts = {'QB': 2, 'RB': 3, 'WR': 4, 'TE': 1}
depth_counts           = {'QB': 3, 'RB': 4, 'WR': 6, 'TE': 2}

# --- GLOBAL STATE ---
draft_state = {
    "picks": [],
    "available_players": [],
    "pick_number": 1,
    "league_users": {},       # roster_id -> username
    "players_df": pd.DataFrame(),
    "pick_to_username": {},
}
team_needs_dict = {}

# --- HELPERS ---
def standardize_name(name: str) -> str:
    return name.strip().upper() if name else ""

def fetch_league_info(league_id: str):
    """Fetch users & rosters once and build mappings."""
    users = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

    # user_id -> display_name
    user_map = {u['user_id']: u['display_name'] for u in users}

    # roster_id -> owner_id, and player_id -> roster_id
    roster_owner = {}
    player_to_roster = {}
    for r in rosters:
        rid = r['roster_id']
        roster_owner[rid] = r['owner_id']
        for pid in r.get('players', []):
            player_to_roster[str(pid)] = rid

    # roster_id -> display_name
    roster_username = {rid: user_map.get(owner, "Unknown") for rid, owner in roster_owner.items()}
    return roster_username, player_to_roster

def fetch_players_with_adp():
    sleeper = requests.get("https://api.sleeper.app/v1/players/nfl").json()
    adp_df  = pd.read_csv(csv_file_path)

    # normalize and cast ADP
    adp_df['player_key'] = adp_df['PLAYER NAME'].str.strip().str.upper()
    adp_df.rename(columns={'AVG.': 'adp', 'POS': 'position'}, inplace=True)
    adp_df['adp'] = pd.to_numeric(adp_df['adp'], errors='coerce')

    rows = []
    for pid, info in sleeper.items():
        pos = info.get('position')
        name = info.get('full_name')
        if not pos or not name or pos not in ['QB','RB','WR','TE']:
            continue

        key = name.strip().upper()
        # grab the first matching ADP value (if any)
        adp_match = adp_df.loc[adp_df['player_key'] == key, 'adp']
        adp_val   = float(adp_match.iloc[0]) if not adp_match.empty else None

        rows.append({
            'player_id': pid,
            'player_name':    key,
            'position':  pos,
            'adp':       adp_val
        })

    return pd.DataFrame(rows)

def build_pick_order(roster_username: dict):
    drafts = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts").json()
    draft_id = drafts[0]['draft_id']
    details = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}").json()

    slot_map = details['slot_to_roster_id']    # e.g. {"1": 123, "2": 456, ...}
    rounds   = details.get('settings', {}).get('rounds', 4)
    total    = len(slot_map)

    pick_to_user = {}
    # normal picks
    for rnd in range(rounds):
        for slot_str, rid in slot_map.items():
            pick = rnd * total + int(slot_str)
            pick_to_user[pick] = roster_username.get(rid, "Unknown")

    # traded picks override
    traded = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/traded_picks").json()
    # build roster_id -> slot index
    slot_index = {rid: int(slot_str) for slot_str, rid in slot_map.items()}
    for t in traded:
        orig_rid = t['roster_id']
        new_rid  = t['owner_id']
        rnd      = t['round']      # 1‑based
        slot     = slot_index.get(orig_rid)
        if slot:
            pick = (rnd - 1) * total + slot
            pick_to_user[pick] = roster_username.get(new_rid, "Unknown")

    return pick_to_user

def calculate_combined_scores(df: pd.DataFrame) -> pd.DataFrame:
    scores = []
    for (user, pos), grp in df.groupby(['username','position']):
        starter = grp.nsmallest(starter_quality_counts.get(pos,0), 'adp')['adp'].mean()
        depth   = grp.nsmallest(    depth_counts.get(pos,0), 'adp')['adp'].mean()
        scores.append({
            'username': user,
            'position': pos,
            'starter_score': starter,
            'depth_score':   depth
        })
    return pd.DataFrame(scores)

def get_positions_to_improve(players_df):
    # 1) compute each team’s starter & depth scores
    combined = calculate_combined_scores(players_df)

    # 2) compute league‑median for each position
    league_avg = (
        combined
        .groupby('position')[['starter_score','depth_score']]
        .median()
        .reset_index()
        .rename(columns={
            'starter_score': 'starter_score_league',
            'depth_score':   'depth_score_league'
        })
    )

    # 3) merge back so each row has both team & league numbers
    comparison = pd.merge(
        combined,
        league_avg,
        on='position',
        how='left'
    )

    # 4) mark who needs improvement
    comparison['improve_starter'] = (
        comparison['starter_score'] > comparison['starter_score_league']
    )
    comparison['improve_depth'] = (
        comparison['depth_score'] > comparison['depth_score_league']
    )

    return comparison

# --- INITIALIZE ---
def initialize_draft():
    global team_needs_dict

    # 1) fetch league ⟷ user & roster mappings
    roster_username, player_to_roster = fetch_league_info(league_id)
    draft_state["league_users"] = roster_username

    # 2) fetch full player list + ADP
    players_df = fetch_players_with_adp()

    # 3) attach roster_id → username
    players_df['roster_id'] = players_df['player_id'].map(player_to_roster)
    players_df['username']  = players_df['roster_id'].map(roster_username)

    # 4) calculate needs from rostered players only
    rostered = players_df.dropna(subset=['username'])
    needs_df = get_positions_to_improve(rostered)

    # build user → [positions to target]
    team_needs = {}
    for _, row in needs_df.iterrows():
        if row['improve_starter'] or row['improve_depth']:
            team_needs.setdefault(row['username'], []).append(row['position'])
    team_needs_dict.clear()
    team_needs_dict.update(team_needs)

    # 5) pick order
    draft_state["pick_to_username"] = build_pick_order(roster_username)

    # 6) free-agent pool = everyone NOT on a roster
    free = (
        players_df
        .loc[players_df['roster_id'].isna(), ['player_name','position','adp']]
        .sort_values('adp')
        .to_dict(orient='records')
    )
    draft_state["available_players"] = free

    # 7) reset picks counter
    draft_state["picks"] = []
    draft_state["pick_number"] = min(draft_state["pick_to_username"].keys())

    # store final players_df
    draft_state["players_df"] = players_df

# --- DRAFT ACTIONS ---
def get_team_on_the_clock():
    return draft_state["pick_to_username"].get(draft_state["pick_number"], "Unknown")

def pick_player(player_name: str):
    global team_needs_dict
    player_name = player_name.strip().upper()
    for p in draft_state["available_players"]:
        if p['player_name'] == player_name:
            team = get_team_on_the_clock()
            draft_state["picks"].append({
                "pick_number": draft_state["pick_number"],
                "player": player_name,
                "position": p['position'],
                "username": team
            })
            # update live needs
            if team in team_needs_dict:
                if p['position'] in team_needs_dict[team]:
                    team_needs_dict[team].remove(p['position'])
                if not team_needs_dict[team]:
                    team_needs_dict[team] = ["Best Available"]

            draft_state["available_players"].remove(p)
            draft_state["pick_number"] += 1
            return
    raise ValueError(f"{player_name} is not available to pick.")

def auto_pick_best():
    """
    Auto‑pick the available player with the lowest ADP.
    Any None or non‑finite ADP is treated as +inf, so real ADP values always win.
    """
    if not draft_state["available_players"]:
        raise ValueError("No available players to auto‑pick")

    def adp_key(player):
        adp = player.get('adp')
        # if it's a finite number, use it; otherwise push it to the back
        return adp if isinstance(adp, (int, float)) and isfinite(adp) else float('inf')

    best = min(draft_state["available_players"], key=adp_key)
    # now delegate into your existing pick logic
    # NOTE: if your rows now use "player_name" instead of "player", adjust accordingly:
    pick_player(best['player_name'])

def reset_draft():
    initialize_draft()

def get_draft_state():
    return {
        "picks": draft_state["picks"],
        "available_players": draft_state["available_players"],
        "on_the_clock": {
            "pick_number": draft_state["pick_number"],
            "team_name": get_team_on_the_clock(),
            "team_needs": team_needs_dict.get(get_team_on_the_clock(), ["Best Available"])
        },
        "pick_to_username": draft_state["pick_to_username"],
        "team_needs": team_needs_dict
    }