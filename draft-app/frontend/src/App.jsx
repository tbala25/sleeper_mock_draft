import React, { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [draftState, setDraftState] = useState(null);
  const [loadingPick, setLoadingPick] = useState(false);
  const pickListRef = useRef(null);

  const fetchDraftState = async () => {
    const res = await fetch('http://127.0.0.1:8000/draft/state');
    const data = await res.json();
    setDraftState(data);
  };

  const makeNextPick = async () => {
    setLoadingPick(true);
    await fetch('http://127.0.0.1:8000/draft/next-pick', { method: 'POST' });
    await fetchDraftState();
    setLoadingPick(false);
  };

  const resetDraft = async () => {
    await fetch('http://127.0.0.1:8000/draft/reset', { method: 'POST' });
    await fetchDraftState();
  };

  const pickPlayer = async (playerName) => {
    await fetch('http://127.0.0.1:8000/draft/pick-player', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: playerName })
    });
    await fetchDraftState();
  };

  useEffect(() => {
    fetchDraftState();
  }, []);

  useEffect(() => {
    // Auto-scroll the pick list to current pick
    if (pickListRef.current && draftState) {
      const activePick = pickListRef.current.querySelector('.pick.on-the-clock');
      if (activePick) {
        activePick.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [draftState]);

  if (!draftState) return <div>Loading draft...</div>;

  const { picks, available_players, on_the_clock, pick_to_username, team_needs } = draftState;

  const getPickContent = (pickNumber) => {
    const pick = picks.find(p => p.pick_number === pickNumber);
    const username = pick_to_username[pickNumber] || "Unknown";
    const needs = team_needs[username] || ["Best Available"];

    if (pick) {
      return `${pick.username}: ${pick.player} (${pick.position})`;
    } else {
      return `${username} - Needs: ${needs.join(', ')}`;
    }
  };

  return (
    <div className="container">
      <h1>🏈 Fantasy Draft Board</h1>

      <div className="on-the-clock-bar">
        Pick {on_the_clock.pick_number} - {on_the_clock.team_name} <br />
        Needs: {on_the_clock.team_needs.join(', ')}
      </div>

      <div className="controls">
        <button onClick={makeNextPick} disabled={loadingPick}>
          {loadingPick ? 'Picking...' : 'Auto Pick Best Player'}
        </button>
        <button onClick={resetDraft}>
          Reset Draft
        </button>
      </div>

      <div className="layout">
        {/* LEFT SIDE: Picks */}
        <div className="draft-picks" ref={pickListRef}>
          {Object.keys(pick_to_username)
            .sort((a, b) => Number(a) - Number(b))
            .map((pickNum) => (
              <div
                key={pickNum}
                className={`pick ${parseInt(pickNum) === on_the_clock.pick_number ? 'on-the-clock' : ''}`}
              >
                <div className="pick-main">Pick {pickNum}</div>
                <div className="needs-text">{getPickContent(Number(pickNum))}</div>
              </div>
          ))}
        </div>

        {/* RIGHT SIDE: Available Players */}
        <div className="available-players">
          <h2>Available Players</h2>
          <ul>
            {available_players
              .sort((a, b) => (a.adp || 9999) - (b.adp || 9999))
              .slice(0, 20)
              .map((player, idx) => (
                <li key={idx}>
                  {player.player_name} {player.position} (ADP: {player.adp})
                  <button onClick={() => pickPlayer(player.player_name)}>Pick</button>
                </li>
              ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default App;