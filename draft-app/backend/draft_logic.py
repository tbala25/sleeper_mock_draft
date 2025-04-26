# backend/draft_logic.py

import requests
import pandas as pd
import requests_cache
import warnings
from math import isfinite

warnings.filterwarnings("ignore")
requests_cache.install_cache('sleeper', expire_after=43200)

# --- CONFIG ---
league_id     = "1180634108313018368"
csv_file_path = "./FantasyPros_2025_Dynasty_OP_Rankings-2.csv"

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
    users   = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users").json()
    rosters = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters").json()

    user_map = {u['user_id']: u['display_name'] for u in users}

    roster_owner     = {}
    player_to_roster = {}
    for r in rosters:
        rid = r['roster_id']
        roster_owner[rid] = r['owner_id']
        for pid in r.get('players', []):
            player_to_roster[str(pid)] = rid

    roster_username = {rid: user_map.get(owner, "Unknown")
                       for rid, owner in roster_owner.items()}
    return roster_username, player_to_roster

def fetch_players_with_adp():
    """Fetch all NFL players and merge in ADP from CSV."""
    sleeper = requests.get("https://api.sleeper.app/v1/players/nfl").json()
    adp_df  = pd.read_csv(csv_file_path)
    adp_df['player_key'] = adp_df['PLAYER NAME'].str.strip().str.upper()
    adp_df.rename(columns={'AVG.': 'adp', 'POS': 'position'}, inplace=True)
    adp_df['adp'] = pd.to_numeric(adp_df['adp'], errors='coerce')

    rows = []
    for pid, info in sleeper.items():
        pos  = info.get('position')
        name = info.get('full_name')
        if not pos or not name or pos not in ['QB','RB','WR','TE']:
            continue
        key = name.strip().upper()
        adp_match = adp_df.loc[adp_df['player_key'] == key, 'adp']
        adp_val   = float(adp_match.iloc[0]) if not adp_match.empty else None
        rows.append({
            'player_id':   pid,
            'player_name': key,
            'position':    pos,
            'adp':         adp_val
        })
    return pd.DataFrame(rows)

def build_pick_order(roster_username: dict):
    drafts   = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/drafts").json()
    draft_id = drafts[0]['draft_id']
    details  = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}").json()

    slot_map = details['slot_to_roster_id']
    rounds   = details.get('settings', {}).get('rounds', 4)
    total    = len(slot_map)

    pick_to_user = {}
    for rnd in range(rounds):
        for slot_str, rid in slot_map.items():
            pick = rnd * total + int(slot_str)
            pick_to_user[pick] = roster_username.get(rid, "Unknown")

    traded = requests.get(f"https://api.sleeper.app/v1/draft/{draft_id}/traded_picks").json()
    slot_index = {rid: int(slot) for slot, rid in slot_map.items()}
    for t in traded:
        orig_rid = t['roster_id']
        new_rid  = t['owner_id']
        rnd      = t['round']      # 1-based
        slot     = slot_index.get(orig_rid)
        if slot is not None:
            pick = (rnd - 1) * total + slot
            pick_to_user[pick] = roster_username.get(new_rid, "Unknown")

    return pick_to_user

def calculate_combined_scores(df: pd.DataFrame) -> pd.DataFrame:
    scores = []
    for (user, pos), grp in df.groupby(['username','position']):
        starter = grp.nsmallest(starter_quality_counts.get(pos,0), 'adp')['adp'].mean()
        depth   = grp.nsmallest(depth_counts.get(pos,0),       'adp')['adp'].mean()
        scores.append({
            'username':     user,
            'position':     pos,
            'starter_score': starter,
            'depth_score':   depth
        })
    return pd.DataFrame(scores)

def get_positions_to_improve(players_df: pd.DataFrame) -> pd.DataFrame:
    combined = calculate_combined_scores(players_df)
    league_avg = (
        combined.groupby('position')[['starter_score','depth_score']]
        .median()
        .reset_index()
        .rename(columns={
            'starter_score': 'starter_score_league',
            'depth_score':   'depth_score_league'
        })
    )
    comp = pd.merge(combined, league_avg, on='position', how='left')
    comp['improve_starter'] = comp['starter_score'] > comp['starter_score_league']
    comp['improve_depth']   = comp['depth_score']   > comp['depth_score_league']
    return comp

# --- INITIALIZE DRAFT ---
def initialize_draft():
    global team_needs_dict

    roster_username, player_to_roster = fetch_league_info(league_id)
    draft_state["league_users"] = roster_username

    players_df = fetch_players_with_adp()
    # attach roster info
    players_df['roster_id'] = players_df['player_id'].map(player_to_roster)
    players_df['username']  = players_df['roster_id'].map(roster_username)

    # compute initial team needs
    rostered = players_df.dropna(subset=['username'])
    needs_df = get_positions_to_improve(rostered)
    team_needs = {}
    for _, row in needs_df.iterrows():
        if row['improve_starter'] or row['improve_depth']:
            team_needs.setdefault(row['username'], []).append(row['position'])
    team_needs_dict.clear()
    team_needs_dict.update(team_needs)

    # build pick order
    draft_state["pick_to_username"] = build_pick_order(roster_username)

    # prepare free-agent list
    free = (
        players_df
        .loc[players_df['roster_id'].isna(), ['player_name','position','adp']]
        .sort_values('adp')
        .to_dict(orient='records')
    )
    draft_state["available_players"] = free

    # init picks and counter
    draft_state["picks"] = []
    draft_state["pick_number"] = min(draft_state["pick_to_username"].keys())

    # store master DataFrame, initialize pick_taken
    players_df['pick_taken'] = pd.NA
    draft_state["players_df"] = players_df

# --- DRAFT ACTIONS ---
def get_team_on_the_clock():
    return draft_state["pick_to_username"].get(draft_state["pick_number"], "Unknown")

def pick_player(player_name: str):
    global team_needs_dict
    name = player_name.strip().upper()

    for p in draft_state["available_players"]:
        if p['player_name'] == name:
            team = get_team_on_the_clock()
            # record the pick
            draft_state["picks"].append({
                "pick_number": draft_state["pick_number"],
                "player":      name,
                "position":    p['position'],
                "username":    team
            })
            # update live needs
            if team in team_needs_dict:
                if p['position'] in team_needs_dict[team]:
                    team_needs_dict[team].remove(p['position'])
                if not team_needs_dict[team]:
                    team_needs_dict[team] = ["Best Available"]
            # remove from UI pool
            draft_state["available_players"].remove(p)
            # mark as taken in master DataFrame
            df = draft_state["players_df"]
            df.loc[df['player_name'] == name, 'pick_taken'] = draft_state["pick_number"]
            # advance pick
            draft_state["pick_number"] += 1
            return

    raise ValueError(f"{name} is not available to pick.")

def find_best_available(draftable_players: pd.DataFrame,
                        user_needs: pd.DataFrame,
                        pick_number: int):
    """
    draftable_players must have columns:
      ['player_name','position','adp','pick_taken']
    user_needs must have ['position','gap'].
    """
    # 0) compute ADP threshold
    best_adp = draftable_players['adp'].min()
    threshold = best_adp + 15

    # 1) sort needs by gap desc
    needs_sorted = user_needs.sort_values(by='gap', ascending=False)

    # 2) try each need in order
    for _, need in needs_sorted.iterrows():
        pos = need['position']

        # take the top-3 by ADP, **then** limit to threshold
        top3 = (
            draftable_players
            .sort_values('adp')
            .head(3)
        )
        top3 = top3[top3['adp'] <= threshold]

        # now filter to this position and still un-picked
        candidates = top3[
            (top3['position'] == pos) &
            (top3['pick_taken'].isna())
        ]
        if not candidates.empty:
            sel = candidates.iloc[0]
            draftable_players.at[sel.name, 'pick_taken'] = pick_number
            return sel['player_name'], pos, sel['adp']

    # 3) fallback: any free agent under the threshold?
    avail = draftable_players[
        draftable_players['pick_taken'].isna() &
        (draftable_players['adp'] <= threshold)
    ]
    if not avail.empty:
        first = avail.sort_values('adp').iloc[0]
    else:
        # if none under threshold, just grab the very best remaining
        first = draftable_players[
            draftable_players['pick_taken'].isna()
        ].sort_values('adp').iloc[0]

    draftable_players.at[first.name, 'pick_taken'] = pick_number
    return first['player_name'], first['position'], first['adp']

def auto_pick_best():
    """Auto-pick based on team needs (gap prioritization)."""
    df = draft_state["players_df"]
    if df.empty:
        raise ValueError("Draft not initialized yet")

    # filter only true free agents not yet picked
    draftable = df[
        df['pick_taken'].isna() &
        df['roster_id'].isna()
    ].copy()
    if draftable.empty:
        raise ValueError("No free agents left to auto-pick")

    # compute gap for each team/position
    combined = calculate_combined_scores(df.dropna(subset=['username']))
    league_avg = (
        combined
        .groupby('position')[['starter_score','depth_score']]
        .median()
        .rename(columns={
            'starter_score':'starter_league',
            'depth_score':'depth_league'
        })
        .reset_index()
    )
    comp = combined.merge(league_avg, on='position')
    comp['gap'] = (
        (comp['starter_league'] - comp['starter_score']).abs() +
        (comp['depth_league']   - comp['depth_score']).abs()
    )
    current    = get_team_on_the_clock()
    user_needs = comp[comp['username'] == current][['position','gap']]

    # pick and delegate
    player_name, _, _ = find_best_available(
        draftable, user_needs, draft_state["pick_number"]
    )
    pick_player(player_name)

def reset_draft():
    initialize_draft()

def get_draft_state():
    return {
        "picks": draft_state["picks"],
        "available_players": draft_state["available_players"],
        "on_the_clock": {
            "pick_number": draft_state["pick_number"],
            "team_name":   get_team_on_the_clock(),
            "team_needs":  team_needs_dict.get(get_team_on_the_clock(), ["Best Available"])
        },
        "pick_to_username": draft_state["pick_to_username"],
        "team_needs":       team_needs_dict
    }