import streamlit as st
import pandas as pd
import numpy as np
from sleeper_draft import *
import subprocess
import plotly.express as px
import time

st.set_page_config(layout="wide")

# Path to the Python interpreter, and the script you want to run
python_script = "sleeper_draft.py"

# Run sleeper_draft.py as a separate process
subprocess.run(["python", python_script])
# Assume all your existing functions are correctly defined here, including data fetching and transformation.

# Your existing league_id and other necessary global variables
#league_id = "1062924204691087360"

# def load_data():
#     # draft_results = run_m()
#     # picks_to_username = get_picks_to_username()
#     # team_score_change = get_team_score_change()
#     # position_score_change = get_position_score_change()
#     # adp_df = get_adp_df()
#     # players_df = get_players_df()
#
#     league_users = get_league_users(league_id)
#     players_df, adp_df, player_id_to_roster_id = get_players()
#     positions_to_improve, league_team_avg = get_positions_to_improve(players_df)
#     preraft_team_score = league_team_avg.copy()
#     predraft_positions_to_improve = positions_to_improve.copy()
#     pick_owners, draft_picks, username_to_picks, pick_to_username = get_draft_picks(league_id)
#     draftable_players = get_draftable_players()
#     draft_results, positions_to_improve, league_team_avg = run_mock_draft()
#     postdraft_team_score, team_score_change, position_score_change = get_postdraft_analysis()
#
#
#
#     return league_users, players_df, adp_df, player_id_to_roster_id, positions_to_improve, \
#            league_team_avg, preraft_team_score, predraft_positions_to_improve, pick_owners, \
#            draft_picks, username_to_picks, pick_to_username, draftable_players, draft_results, \
#            positions_to_improve, league_team_avg, postdraft_team_score, team_score_change, \
#            position_score_change

def app():

    custom_color_scale = [
        [0, 'rgb(26, 38, 60)'],  # Midpoint of the scale blue
        [.5, 'rgb(98, 113, 221)'],  # End of the scale purple
        [1, 'rgb(93, 203, 184)'],  # Start of the scale green

    ]

    #draft_results, picks_to_username, team_score_change, position_score_change, adp_df, players_df = load_data()
    # Filter options
    positions = sorted(players_df['position'].unique())
    users = players_df['username'].unique()
    position_filter = st.multiselect("Filter by Position", positions, default=positions)
    user_filter = st.multiselect("Filter by Username", users, default=users)

    # Function to color code the DataFrame
    def color_code(val):
        color = 'red' if val > 120 else ('orange' if val > 75 else 'green')
        return f'background-color: {color}'

    def interpolate_color(val, vmin, vmax):
        if vmax == vmin:  # Avoid division by zero
            return custom_color_scale[1][1]  # Return the midpoint color if all values are the same

        # Find proportion of val within range
        proportion = (val - vmin) / (vmax - vmin)

        # Determine which segment of the color scale to use
        if proportion < 0.5:
            # Scale proportion from [0, 0.5] to [0, 1]
            proportion *= 2
            start_color = np.array([int(c) for c in custom_color_scale[0][1][4:-1].split(',')])
            end_color = np.array([int(c) for c in custom_color_scale[1][1][4:-1].split(',')])
        else:
            # Scale proportion from [0.5, 1] to [0, 1]
            proportion = (proportion - 0.5) * 2
            start_color = np.array([int(c) for c in custom_color_scale[1][1][4:-1].split(',')])
            end_color = np.array([int(c) for c in custom_color_scale[2][1][4:-1].split(',')])

        # Interpolate color
        color = start_color + (end_color - start_color) * proportion
        return f'background-color: rgb({color[0]}, {color[1]}, {color[2]})'

    # Color code the DataFrame based on the custom color scale
    def apply_custom_color_scale(val):
        vmin = 5
        vmax = 350
        return interpolate_color(val, vmin, vmax)


    st.header('Pre Draft Team Needs')
    st.caption('Teams analyzed on average ADP of Starter (2QB, 3RB, 4WR, 1TE) and Depth (3QB, 4RB, 6WR, 2TE) players')

    predraft_positions_to_improve['improve_starter'] = predraft_positions_to_improve['improve_starter'] * 1
    predraft_positions_to_improve['improve_depth'] = predraft_positions_to_improve['improve_depth'] * 1

    st.dataframe(predraft_positions_to_improve.sort_values(by='gap', ascending=False))


    # Displaying each DataFrame with optional filtering and color coding
    st.subheader("Draft Results")
    filtered_draft_results = draft_results[draft_results['position'].isin(position_filter) & draft_results['username'].isin(user_filter)]
    filtered_draft_results.style.applymap(apply_custom_color_scale, subset=['adp'])
    filtered_draft_results['adp'] = filtered_draft_results['adp'].round(2)

    # First, round the 'adp' values in the DataFrame
    filtered_draft_results['adp'] = filtered_draft_results['adp'].round(2)

    # Then, apply the color coding and format the 'adp' column for display
    styled_df = (
        filtered_draft_results.style
        .applymap(apply_custom_color_scale, subset=['adp'])  # Apply color coding to 'adp' column
        .format({'adp': '{:.1f}'})  # Ensure 'adp' values are displayed with 2 decimal places
    )

    st.dataframe(styled_df)
    # st.subheader("Picks to Username")
    # filtered_picks_to_username = pick_to_username[pick_to_username['username'].isin(user_filter)]
    # st.dataframe(filtered_picks_to_username)

    team_score_change['starter_improvement'] = team_score_change['starter_improvement'] * -1
    team_score_change['depth_improvement'] = team_score_change['depth_improvement'] * -1

    # Starter vs. Depth Improvement Scatterplot
    st.header('Post Draft Team Improvement')
    st.caption('ADP Data pulled from FantasyPros.com')

    fig1 = px.scatter(team_score_change, x='starter_improvement', y='depth_improvement',
                      hover_name='username', size='postdraft_starter_score',
                      color='postdraft_starter_score', color_continuous_scale=custom_color_scale,
                      title='Starter vs. Depth Improvement')
    fig1.update_layout(legend_traceorder="reversed")

    st.plotly_chart(fig1, use_container_width=True)

    tab1, tab2, = st.tabs(["Chart", "Data Table"])

    with tab1:
        # Postdraft Scores Scatterplot
        st.header('Overall Strength of Team')

        fig2 = px.scatter(team_score_change, x='postdraft_starter_score', y='postdraft_depth_score',
                          hover_name='username', title='Postdraft Starter vs. Depth Scores',
                          color='predraft_starter_score', size='predraft_depth_score',
                          color_continuous_scale=custom_color_scale)
        fig2.update_yaxes(autorange="reversed")
        fig2.update_xaxes(autorange="reversed")
        #fig2.update_layout(legend_traceorder="reversed")

        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.subheader("Team Score Change")
        filtered_team_score_change = team_score_change[team_score_change['username'].isin(user_filter)]
        st.dataframe(filtered_team_score_change.style.applymap(color_code, subset=['starter_improvement', 'depth_improvement']))

    st.subheader("Position Score Change")
    filtered_position_score_change = position_score_change[(position_score_change['position'].isin(position_filter)) & (position_score_change['username'].isin(user_filter))]
    st.dataframe(filtered_position_score_change.style.applymap(color_code, subset=['starter_score_diff', 'depth_score_diff']))

    st.subheader("ADP DataFrame")
    filtered_adp_df = adp_df[adp_df['position'].isin(position_filter)]
    st.dataframe(filtered_adp_df.style.applymap(color_code, subset=['adp']))



    # st.subheader("Players DataFrame")
    # filtered_players_df = players_df[(players_df['position'].isin(position_filter)) & (players_df['username'].isin(user_filter))]
    # st.dataframe(filtered_players_df.style.applymap(color_code, subset=['adp']))

if __name__ == "__main__":

    st.title(':rainbow[_The Best Dynasty FF App (WIP)_] :sunglasses: :football: :european_castle: :crossed_swords:')

    league_id = st.text_input(label='Enter Sleeper League ID')

    if league_id is not '':





        adp_df = None
        while adp_df is None:
            # fake loading bar1
            progress_text = "Gathering info on your league..."
            my_bar = st.progress(0, text=progress_text)

            for percent_complete in range(100):
                time.sleep(0.01)
                my_bar.progress(percent_complete + 1, text=progress_text)
            time.sleep(1)
            my_bar.empty()

            ######### GET USERS ##################
            # get user_id,team_id,username
            league_users = get_league_users(league_id)

            ############ GET PLAYERS ############

            players_df, adp_df, player_id_to_roster_id = get_players(league_id, league_users)

        pick_to_username = None
        while pick_to_username is None:
            ########### IDENTIFY TEAM NEEDS################

            # fake loading bar2
            progress_text = "Analyzing team needs and strengths..."
            my_bar = st.progress(0, text=progress_text)

            for percent_complete in range(100):
                time.sleep(0.1)
                my_bar.progress(percent_complete + 1, text=progress_text)
            time.sleep(1)
            my_bar.empty()

            # Example usage (Assuming calculate_combined_scores and players_df are defined)
            positions_to_improve, league_team_avg = get_positions_to_improve(players_df)
            preraft_team_score = league_team_avg.copy()
            predraft_positions_to_improve = positions_to_improve.copy()

            ###############GET DRAFT PICKS###################
            pick_owners, draft_picks, username_to_picks, pick_to_username = get_draft_picks(league_id, league_users)

        draft_results = None
        while draft_results is None:
            # fake loading bar3
            progress_text = "Mock drafting..."
            my_bar = st.progress(0, text=progress_text)

            for percent_complete in range(100):
                time.sleep(0.1)
                my_bar.progress(percent_complete + 1, text=progress_text)
            time.sleep(1)
            my_bar.empty()

            ####DRAFTABLE PLAYERS#########

            draftable_players = get_draftable_players(adp_df)

            ######### MOCK DRAFT ##########

            draft_results, positions_to_improve, league_team_avg = run_mock_draft(draftable_players, pick_to_username,
                                                                                  positions_to_improve, players_df)

            ###### POST DRAFT ANALYSIS ######
            postdraft_team_score, team_score_change, position_score_change = get_postdraft_analysis(league_team_avg,
                                                                                                    preraft_team_score,
                                                                                                    predraft_positions_to_improve,
                                                                                                    positions_to_improve)

        ###### BUILD APP ######
        app()
