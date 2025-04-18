import pandas as pd
import random


class DraftManager:
    def __init__(self):
        self.load_data()
        self.pick_number = 1
        self.picks = []

    def load_data(self):
        self.players = pd.read_csv("FantasyPros_2025_Dynasty_OP_Rankings.csv")
        self.players['pick_taken'] = None
        # Team needs are randomized for fun now (real logic can be added)
        self.team_needs = {i: random.choice(["QB", "RB", "WR", "TE"]) for i in range(1, 100)}

    def make_next_pick(self):
        available = self.players[self.players['pick_taken'].isna()]
        if available.empty:
            return {"error": "No players left"}

        best_player = available.sort_values('AVG.').iloc[0]
        return self._make_pick(best_player)

    def pick_specific_player(self, player_name):
        available = self.players[self.players['pick_taken'].isna()]
        selected = available[available['PLAYER NAME'] == player_name]
        if selected.empty:
            return {"error": "Player not available"}

        best_player = selected.iloc[0]
        return self._make_pick(best_player)

    def _make_pick(self, best_player):
        player_name = best_player['PLAYER NAME']
        position = best_player['POS']

        idx = best_player.name
        self.players.at[idx, 'pick_taken'] = self.pick_number

        pick_info = {
            "pick_number": self.pick_number,
            "player": player_name,
            "position": position,
            "team_need": self.team_needs.get(self.pick_number, "Best Available")
        }
        self.picks.append(pick_info)
        self.pick_number += 1

        return pick_info

    def get_current_state(self):
        return {
            "picks": self.picks,
            "available_players": self.players[self.players['pick_taken'].isna()][['PLAYER NAME', 'POS']].to_dict(
                orient='records'),
            "on_the_clock": {
                "pick_number": self.pick_number,
                "team_need": self.team_needs.get(self.pick_number, "Best Available")
            }
        }

    def reset(self):
        self.load_data()
        self.pick_number = 1
        self.picks = []
