import requests
import requests_cache
import pandas as pd

requests_cache.install_cache('sleeper', expire_after=43200) #12 hour cache

league_id = "1062924204691087360"


def get_draft_picks(league_id):
    """Fetch all draft picks for the league, including details about traded picks."""
    # Fetch the draft ID(s) for the league
    drafts_url = f"https://api.sleeper.app/v1/league/{league_id}/drafts"
    drafts_response = requests.get(drafts_url, verify=False)  # Note: verify=False is for demonstration and troubleshooting
    draft_id = drafts_response.json()[0]['draft_id']  # Assuming the first draft is relevant
    
    # Fetch draft details, including slot_to_roster_id mappings
    draft_details_url = f"https://api.sleeper.app/v1/draft/{draft_id}"
    draft_details_response = requests.get(draft_details_url, verify=False)  # Note: verify=False is for demonstration and troubleshooting
    draft_details = draft_details_response.json()
    
    # Mapping of slot numbers to roster IDs (which team owns each original draft slot)
    slot_to_roster_id = draft_details['slot_to_roster_id']
    roster_id_to_slot = dict([(value, key) for key, value in slot_to_roster_id.items()])
    draft_rounds = 4
    #pick_numbers = {}
    pick_owners = {}

    # for d in range(draft_rounds):
    #     for slot in slot_to_roster_id:
    #         pick_numbers[int(d*12)+int(slot)] = slot_to_roster_id[slot]

    for slot in slot_to_roster_id:
        v = slot_to_roster_id[slot]
        for d in range(draft_rounds):
            if pick_owners.get(v) is not None:
                pick_owners[v] = list(pick_owners.get(v)) + [int(d*12)+int(slot)]
            else:
                pick_owners[v] = [int(d*12)+int(slot)]

    # Fetch traded picks to adjust the slot_to_roster_id mapping accordingly
    traded_picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/traded_picks"
    traded_picks_response = requests.get(traded_picks_url, verify=False)  # Note: verify=False is for demonstration and troubleshooting
    traded_picks = traded_picks_response.json()
    # Update the slot_to_roster_id mapping based on traded picks
    for traded_pick in traded_picks:
        # Assuming 'previous_owner_id' and 'new_owner_id' are the keys indicating the trade details
        # and 'round' and 'pick_no' (or similar) indicate the specific pick traded
        # This part of the code will depend on the exact structure of the traded picks data
        # You might need a more sophisticated method if picks can be traded multiple times

        prev_owner = traded_pick['previous_owner_id']
        new_owner_id = traded_pick['owner_id']
        orig_owner = traded_pick['roster_id'] # used to get what the picknumber is
        pick_round = traded_pick['round']

        pick_to_move = int(roster_id_to_slot[orig_owner]) + ((pick_round-1)*12)

        pick_owners[orig_owner].remove(pick_to_move)
        pick_owners[new_owner_id].append(pick_to_move)

    
    # Return the updated mapping
    return pick_owners



def fetch_league_users_and_rosters(league_id):
    """Fetch league users and rosters and return a DataFrame with the mapping."""
    # Endpoints for league users and rosters
    users_url = f"https://api.sleeper.app/v1/league/{league_id}/users"
    rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"

    # Fetching users
    users_response = requests.get(users_url)
    users_data = users_response.json()

    # Fetching rosters
    rosters_response = requests.get(rosters_url)
    rosters_data = rosters_response.json()

    # Mapping user_id to username
    user_id_to_username = {user['user_id']: user['display_name'] for user in users_data}

    # Preparing data for DataFrame
    data = []
    for roster in rosters_data:
        user_id = roster['owner_id']
        roster_id = roster['roster_id']
        username = user_id_to_username.get(user_id, "Unknown")
        # # Assuming 'teamname' can be derived here; if not, adjust accordingly
        # teamname = "Team Name Placeholder"  # Adjust based on actual data availability
        data.append({'roster_id': roster_id, 'user_id': user_id, 'username': username})

    # Creating DataFrame
    df = pd.DataFrame(data)

    return df


def fetch_players_details():
    """
    Fetch detailed information for all players. This is a placeholder function.
    Depending on the Sleeper API, you might need to download a large dataset once
    and filter it locally, or make individual requests if the API supports it.
    """
    players_url = "https://api.sleeper.app/v1/players/nfl"  # Hypothetical endpoint
    response = requests.get(players_url)
    players_data = response.json()

    # Convert to a list of dicts format expected by the rest of the script
    # Assuming each player's data in players_data includes 'player_id', 'position', and 'name'
    players_details = [
        {"player_id": pid, "position": details.get("position"), "player_name": details.get("full_name")}
        for pid, details in players_data.items()
    ]
    return players_details


def standardize_name(name):
    """Simple function to standardize player names for better matching."""
    # Example standardization, adjust based on actual data format
    return name.strip().upper()


def fetch_players_details_and_adp():
    """
    Fetch player details and combine with ADP data from the uploaded CSV based on player names.
    """
    players_details = fetch_players_details()  # Fetch player details as before

    # Standardize player names in the ADP DataFrame for better matching
    adp_df['Player'] = adp_df['PLAYER NAME'].apply(standardize_name)

    # Convert ADP DataFrame to a dict for easy lookup by standardized player name
    adp_dict = pd.Series(adp_df['AVG.'].values, index=adp_df.Player).to_dict()

    # Add ADP to player details based on standardized player name
    for player in players_details:
        try:
            standardized_name = standardize_name(player["player_name"])
        except:
            print(player)
        player["ADP"] = adp_dict.get(standardized_name, None)

    return players_details

# Function to apply for each row in DataFrame to fetch roster_id
def get_roster_id(player_id):
    return player_id_to_roster_id.get(player_id, None)


# Function to calculate both starter and depth scores
def calculate_combined_scores(df):
    scores_list = []
    # Filter out rows without a username
    filtered_df = df.dropna(subset=['username'])
    for (username, position), group in filtered_df.groupby(['username', 'position']):
        # Calculate starter score
        starter_quality_players = group.nsmallest(starter_quality_counts[position], 'ADP')
        starter_score = starter_quality_players['ADP'].mean()

        # Calculate depth score
        depth_players = group.nsmallest(depth_counts[position], 'ADP')
        depth_score = depth_players['ADP'].mean()

        scores_list.append({
            'username': username,
            'position': position,
            'starter_score': starter_score,
            'depth_score': depth_score
        })

    return pd.DataFrame(scores_list)

#########GET TEAM NAMES#####################
# get user_id,team_id,username
teams_df = fetch_league_users_and_rosters(league_id)
print(teams_df)


############GET PLAYERS############

# Path to the uploaded CSV file
csv_file_path = './FantasyPros_2024_Dynasty_OP_Rankings.csv'

# Read the CSV file into a DataFrame
adp_df = pd.read_csv(csv_file_path)

# Assuming fetch_players_details fetches player details as before
players_details_adp = fetch_players_details_and_adp()
players_df = pd.DataFrame(players_details_adp)
players_df = players_df.dropna()
print(players_df.head())

#add roster id to players_df
rosters_url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
rosters_response = requests.get(rosters_url)
rosters_data = rosters_response.json()

# Initialize an empty dictionary to hold the mapping
player_id_to_roster_id = {}

# Populate the dictionary with player_id to roster_id mapping
for roster in rosters_data:
    for player_id in roster.get('players', []):
        # Ensure player_id is a string if your DataFrame has player_id as string
        player_id_to_roster_id[str(player_id)] = roster['roster_id']

# Add 'roster_id' column
players_df['roster_id'] = players_df['player_id'].apply(get_roster_id)

#add username
# Convert roster_id in player_df to int for matching
#players_df['roster_id'] = players_df['roster_id'].astype(int)
players_df = pd.merge(players_df, teams_df[['roster_id', 'username']], on='roster_id', how='left')

print(players_df.head())

########### IDENTIFY TEAM NEEDS################
# Define the counts for the starter quality and depth for each position
starter_quality_counts = {'QB': 2, 'RB': 3, 'WR': 4, 'TE': 1}
depth_counts = {'QB': 3, 'RB': 4, 'WR': 6, 'TE': 2}

# Calculate scores and create the combined DataFrame
combined_scores_df = calculate_combined_scores(players_df)
print(combined_scores_df)

#calculate league avg
league_pos_avg = combined_scores_df.groupby('position')[['starter_score', 'depth_score']].median().reset_index()
print(league_pos_avg)

#calculate team avg
teams_avg = combined_scores_df.groupby('username')[['starter_score', 'depth_score']].median().reset_index()
print(teams_avg)

#now do team needs
# Merge the individual team scores with the league averages
comparison_df = pd.merge(combined_scores_df, league_pos_avg, on='position', suffixes=('_team', '_league'))

# Identify positions for improvement
comparison_df['improve_starter'] = comparison_df['starter_score_team'] > comparison_df['starter_score_league']
comparison_df['improve_depth'] = comparison_df['depth_score_team'] > comparison_df['depth_score_league']

# Filter positions that need improvement
positions_to_improve = comparison_df[(comparison_df['improve_starter']) | (comparison_df['improve_depth'])]

print(positions_to_improve[['username', 'position', 'improve_starter', 'improve_depth']])


###############GET DRAFT PICKS###################
pick_owners = get_draft_picks(league_id)
#print(pick_owners)

draft_picks= {}
for keys,values in pick_owners.items():
    for i in values:
        draft_picks[i]=keys
draft_picks = dict(sorted(draft_picks.items()))
#print(draft_picks)

# Convert DataFrame to roster_id to username mapping
roster_id_to_username = pd.Series(teams_df.username.values,index=teams_df.roster_id).to_dict()

# Transform keys in the original dictionary
username_to_picks = {roster_id_to_username.get(k, "Unknown"): v for k, v in pick_owners.items()}

print(username_to_picks)

# Transform keys in the original dictionary
pick_to_username = {pick: roster_id_to_username.get(team_id, "Unknown") for pick, team_id in draft_picks.items()}
print(pick_to_username)


####DRAFTABLE PLAYERS#########
# Sort adp_df by ADP, filter for 'FA' team, and select the top 100
draftable_players= adp_df.sort_values(by='AVG.')[adp_df['TEAM'] == 'FA'].head(100)

print(draftable_players)



##########MOCK DRAFT

import pandas as pd

# Assuming draftable_players, positions_to_improve, and draft_picks are already defined

# Ensure draftable_players is sorted by ADP
draftable_players = draftable_players.sort_values(by='AVG.')

# Initialize columns for pick_taken and username in draftable_players
draftable_players['pick_taken'] = None
draftable_players['username'] = None


# Function to find the best available player based on team needs
# def find_best_available(draftable_players, positions_needed, pick_number):
#     top_available = draftable_players[draftable_players['pick_taken'].isna()].head(5)
#     for _, row in top_available.iterrows():
#         if row['POS'][:2] in positions_needed:
#             draftable_players.at[row.name, 'pick_taken'] = pick_number
#             return row['Player'], row['POS'][:2]
#     # If no specific needs are met, pick the top available player
#     first_available = top_available.iloc[0]
#     draftable_players.at[first_available.name, 'pick_taken'] = pick_number
#     return first_available['Player'], first_available['POS'][:2]

def find_best_available(draftable_players, user_needs, pick_number):
    # Sort user needs by the gap to prioritize higher gaps
    user_needs_sorted = user_needs.sort_values(by='gap', ascending=False)

    for _, need_row in user_needs_sorted.iterrows():
        position = need_row['position']
        # Filter the top 5 available players and then for the specific position
        top_available = draftable_players.head(5)
        top_available = top_available[(top_available['pick_taken'].isna()) &
                                          (top_available['POS'].apply(lambda x: x[:2]) == position)]
        if not top_available.empty:
            # Select the player with the lowest ADP within the top 5 available players for the needed position
            selected_player_row = top_available.iloc[0]
            draftable_players.at[selected_player_row.name, 'pick_taken'] = pick_number
            return selected_player_row['Player'], position

    # If no players match the prioritized needs based on the gap, select the top available player overall
    first_available = draftable_players[draftable_players['pick_taken'].isna()].head(1).iloc[0]
    draftable_players.at[first_available.name, 'pick_taken'] = pick_number
    return first_available['Player'], first_available['POS'][:2]


# Mock draft simulation
for pick_number, username in pick_to_username.items():
    # Determine if the pick is for a starter or depth player
    pick_type = 'improve_starter' if pick_number <= 26 else 'improve_depth'

    # Get positions to improve for the current user
    user_needs = positions_to_improve[(positions_to_improve['username'] == username) &
                                      (positions_to_improve[pick_type])]
    user_needs['gap'] = (user_needs['starter_score_team'] - user_needs['starter_score_league']) + \
                        user_needs['depth_score_team'] - user_needs['depth_score_league']
    # Get the list of positions that need improvement

    # positions_needed = user_needs.sort_values(by='gap', ascending=False)['position'].tolist()

    # Find the best available player based on the team's needs
    player_selected, position_selected = find_best_available(draftable_players, user_needs, pick_number)

    # Assign the username to the selected player
    draftable_players.loc[draftable_players['pick_taken'] == pick_number, 'username'] = username

    print(f"Pick {pick_number} by {username}: {player_selected} ({position_selected})")

# Review the draft results
print(draftable_players[draftable_players['pick_taken'].notna()][
          ['Player', 'POS', 'AVG.', 'pick_taken', 'username']])


#iteratively  update needs after draft pick
#balance AVG. with gap  to decide pick

#find interactivity with setting picks

#test scenarios
