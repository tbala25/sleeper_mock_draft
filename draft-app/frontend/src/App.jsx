import { useState, useEffect } from 'react'
import './App.css'
import React from 'react';


function App() {
  const [draftState, setDraftState] = useState(null);
  const [loadingPick, setLoadingPick] = useState(false);

  const fetchDraftState = async () => {
    const res = await fetch('http://127.0.0.1:8000/draft/state');
    const data = await res.json();
    setDraftState(data);
  }

  const makeNextPick = async () => {
    setLoadingPick(true);
    await fetch('http://127.0.0.1:8000/draft/next-pick', { method: 'POST' });
    await fetchDraftState();
    setLoadingPick(false);
  }

  const resetDraft = async () => {
    await fetch('http://127.0.0.1:8000/draft/reset', { method: 'POST' });
    await fetchDraftState();
  }

  const pickPlayer = async (playerName) => {
    await fetch('http://127.0.0.1:8000/draft/pick-player', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: playerName })
    });
    await fetchDraftState();
  }

  useEffect(() => {
    fetchDraftState();
  }, []);

  if (!draftState) return <div>Loading...</div>

  return (
    <div className="container">
      <h1>🏈 Fantasy Draft Board</h1>

      <div className="controls">
        <button onClick={makeNextPick} disabled={loadingPick}>
          {loadingPick ? 'Picking...' : 'Auto Pick Best Player'}
        </button>

        <button onClick={resetDraft}>
          Reset Draft
        </button>
      </div>

      <div className="clock">
        <h2>Pick {draftState.on_the_clock.pick_number}</h2>
        <h3>Need: {draftState.on_the_clock.team_need}</h3>
      </div>

      <div className="board">
        <h2>Draft Picks</h2>
        <ul>
          {draftState.picks.map(pick => (
            <li key={pick.pick_number}>
              Pick {pick.pick_number}: {pick.player} ({pick.position})
            </li>
          ))}
        </ul>
      </div>

      <div className="players">
        <h2>Available Players</h2>
        <ul>
          {draftState.available_players.slice(0, 20).map((player, idx) => (
            <li key={idx}>
              {player['PLAYER NAME']} ({player.POS})
              <button onClick={() => pickPlayer(player['PLAYER NAME'])}>Pick</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export default App
