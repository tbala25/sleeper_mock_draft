import React, { useState, useEffect, useRef } from 'react';
import './App.css';

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
      body: JSON.stringify({ player_name: playerName }),
    });
    await fetchDraftState();
  };

  useEffect(() => {
    fetchDraftState();
  }, []);

  useEffect(() => {
    if (pickListRef.current && draftState) {
      const el = pickListRef.current.querySelector('.pick.on-the-clock');
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [draftState]);

  if (!draftState) return <div className="loading">Loading draft...</div>;

  const {
    picks,
    available_players,
    on_the_clock: otc,
    pick_to_username,
    team_needs,
  } = draftState;

  const getPickContent = (numStr) => {
    const num = Number(numStr);
    const pick = picks.find(p => p.pick_number === num);
    const user = pick_to_username[numStr] || 'Unknown';
    const needs = team_needs[user] || ['Best Available'];

    return pick
      ? `${pick.username}: ${pick.player} (${pick.position})`
      : `${user} – Needs: ${needs.join(', ')}`;
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-left">
          <span className="logo">🏈</span>
          <h1 className="title">Fantasy Draft Board</h1>
        </div>
        <div className="header-search">
          <input type="text" placeholder="Search players or teams…" />
          <span className="search-icon">🔍</span>
        </div>
      </header>

      <div className="on-the-clock-bar">
        Pick {otc.pick_number} – {otc.team_name}
        <br />
        Needs: {otc.team_needs.join(', ')}
      </div>

      <div className="controls">
        <button onClick={makeNextPick} disabled={loadingPick}>
          {loadingPick ? 'Picking…' : 'Auto Pick Best Player'}
        </button>
        <button onClick={resetDraft}>Reset Draft</button>
      </div>

      <div className="layout">
        {/* LEFT COLUMN */}
        <div className="draft-picks" ref={pickListRef}>
          {Object.keys(pick_to_username)
            .sort((a, b) => Number(a) - Number(b))
            .map(numStr => {
              const num = Number(numStr);
              const isClock = num === otc.pick_number;
              const pick = picks.find(p => p.pick_number === num);
              const posClass = pick ? pick.position.toLowerCase() : '';
              return (
                <div
                  key={numStr}
                  className={`pick ${posClass}${isClock ? ' on-the-clock' : ''}`}
                >
                  <div className="pick-main">Pick {num}</div>
                  <div className="needs-text">{getPickContent(numStr)}</div>
                </div>
              );
            })}
        </div>

        {/* RIGHT COLUMN */}
        <div className="available-players">
          <h2>Available Players</h2>
          <ul>
            {available_players
              .sort((a, b) => (a.adp || 9999) - (b.adp || 9999))
              .map((p, i) => (
                <li
                  key={i}
                  className={p.position.toLowerCase()}
                  onClick={() => pickPlayer(p.player_name)}
                >
                  <span>
                    {p.player_name} {p.position} (ADP: {p.adp})
                  </span>
                  <button>Pick</button>
                </li>
              ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default App;