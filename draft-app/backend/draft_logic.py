# backend/draft_logic.py

import requests
import pandas as pd
import requests_cache
import warnings

warnings.filterwarnings("ignore")
requests_cache.install_cache('sleeper', expire_after=43200)

# --- CONFIG ---
league_id = "1180634108313018368"  # <-- replace with your real league ID
csv_file_path = "./FantasyPros_2025_Dynasty_OP_Rankings.csv"

starter_quality_counts = {'QB': 2, 'RB': 3, 'WR': 4, 'TE': 1}
depth_counts = {'QB': 3, 'RB': 4, 'WR': 6, 'TE': 2}

# --- GLOBAL DRAFT STATE ---
draft_state = {
    "picks": [],
    "available_players": [],
    "pick_number": 1,
    "league_users": {},
    "players_df": pd.DataFrame(),
    "pick_to_username": {}
}

# --- INIT FUNCTION ---
def initialize_draft():
    global draft_state

    league_users = fetch_league_users(league_id)
    players_df = fetch_players_details_and_adp()
    players_df = players_df.dropna()
    print(players_df.columns)

    players_df = players_df[players_df['position_x'].isin(['QB', 'RB', 'WR', 'TE'])]
    players_df['player_name'] = players_df['player_name'].str.strip().str.upper()

    draft_state["available_players"] = players_df.to_dict(orient="records")
    draft_state["picks"] = []
    draft_state["pick_number"] = 1
    draft_state["league_users"] = league_users
    draft_state["players_df"] = players_df
    draft_state["pick_to_username"] = build_pick_order(league_id)

# --- HELPERS ---

def fetch_league_users(league_id):
    users_url = f"https://api.sleeper.app/v1/league/{league_id}/users"
    rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"

    users_response = requests.get(users_url)
    users_data = users_response.json()

    rosters_response = requests.get(rosters_url)
    rosters_data = rosters_response.json()

    user_id_to_username = {user['user_id']: user['display_name'] for user in users_data}

    roster_id_to_username = {}
    for roster in rosters_data:
        user_id = roster['owner_id']
        roster_id = roster['roster_id']
        username = user_id_to_username.get(user_id, "Unknown")
        roster_id_to_username[roster_id] = username

    return roster_id_to_username

def fetch_players_details_and_adp():
    # Fetch real Sleeper NFL players
    players_url = "https://api.sleeper.app/v1/players/nfl"
    response = requests.get(players_url)
    players_data = response.json()

    # Pull real FantasyPros ADP rankings
    adp_df = pd.read_csv(csv_file_path)
    adp_df['player_name'] = adp_df['PLAYER NAME'].str.strip().str.upper()
    adp_df['adp'] = adp_df['AVG.']
    adp_df['position'] = adp_df['POS'].apply(lambda x: x[:2])

    # Fetch league rosters to know which players are already owned
    rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
    rosters_response = requests.get(rosters_url)
    rosters_data = rosters_response.json()

    owned_player_ids = set()
    for roster in rosters_data:
        owned_player_ids.update(roster.get('players', []))

    # Build available players list
    available_players = []

    for player_id, info in players_data.items():
        if player_id in owned_player_ids:
            continue  # Already drafted

        position = info.get("position")
        full_name = info.get("full_name")

        if not position or not full_name:
            continue

        # Only focus on QB, RB, WR, TE
        if position not in ['QB', 'RB', 'WR', 'TE']:
            continue

        available_players.append({
            "player_id": player_id,
            "player_name": full_name.strip().upper(),
            "position": position
        })

    # Convert available players to DataFrame
    available_df = pd.DataFrame(available_players)

    # Merge FantasyPros ADP onto available Sleeper players
    merged_df = pd.merge(
        available_df,
        adp_df[['player_name', 'adp', 'position']],  # ADP position
        how='left',
        on='player_name'
    )

    return merged_df


def build_pick_order(league_id):
    drafts_url = f"https://api.sleeper.app/v1/league/{league_id}/drafts"
    drafts_response = requests.get(drafts_url)
    draft_id = drafts_response.json()[0]['draft_id']

    draft_details_url = f"https://api.sleeper.app/v1/draft/{draft_id}"
    draft_details_response = requests.get(draft_details_url)
    draft_details = draft_details_response.json()

    slot_to_roster_id = draft_details['slot_to_roster_id']
    roster_id_to_username = draft_state["league_users"]

    # Build base pick_to_username
    pick_to_username = {}

    rounds = draft_details.get('settings', {}).get('rounds', 4)  # assume 4 rounds
    draft_slots = len(slot_to_roster_id)

    # Map slot_to_roster_id reversed
    roster_id_to_slot = {v: int(k) for k, v in slot_to_roster_id.items()}

    # Base pick_to_username
    for round_num in range(rounds):
        for slot, roster_id in slot_to_roster_id.items():
            pick_number = (round_num * draft_slots) + int(slot)
            pick_to_username[pick_number] = roster_id_to_username.get(roster_id, "Unknown")

    # Apply traded picks correctly
    traded_picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/traded_picks"
    traded_picks_response = requests.get(traded_picks_url)
    traded_picks = traded_picks_response.json()

    for traded in traded_picks:
        owner_id = traded['owner_id']  # New owner's roster_id
        roster_id_original = traded['roster_id']  # Original roster_id
        round_num = traded['round']

        slot = roster_id_to_slot.get(roster_id_original)

        if slot is not None:
            pick_number = (round_num - 1) * draft_slots + slot
            owner_username = draft_state["league_users"].get(owner_id, "Unknown")
            pick_to_username[pick_number] = owner_username

    return pick_to_username

def get_team_on_the_clock():
    pick_number = draft_state["pick_number"]
    return draft_state["pick_to_username"].get(pick_number, "Unknown")

def find_best_available_for_user(username):
    top_players = sorted(
        [p for p in draft_state["available_players"] if pd.isna(p.get("pick_taken"))],
        key=lambda p: p.get('adp', 9999)
    )

    for player in top_players:
        return player  # simple for now — just best ADP

    return None

# --- DRAFT ACTIONS ---

def pick_player(player_name, username):
    player_name = player_name.strip().upper()
    available = draft_state["available_players"]

    for p in available:
        print(p)
        if p['player_name'] and p['player_name'].strip().upper() == player_name:
            draft_state["picks"].append({
                "pick_number": draft_state["pick_number"],
                "player": p['player_name'],
                "position": p['position_x'],
                "username": username
            })
            p['pick_taken'] = draft_state["pick_number"]
            draft_state["pick_number"] += 1
            return

def auto_pick_next():
    username = get_team_on_the_clock()
    player = find_best_available_for_user(username)

    if player:
        pick_player(player['player_name'], username)

def reset_draft():
    initialize_draft()

def get_draft_state():
    username = get_team_on_the_clock()

    return {
        "picks": draft_state["picks"],
        "available_players": draft_state["available_players"],
        "on_the_clock": {
            "pick_number": draft_state["pick_number"],
            "team_need": username
        }
    }
