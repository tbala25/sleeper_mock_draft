import React from 'react'
import { useState, useEffect } from 'react'
import './App.css'


function App() {
  const [draftState, setDraftState] = useState(null)
  const [loadingPick, setLoadingPick] = useState(false)

  const fetchDraftState = async () => {
    const res = await fetch('http://127.0.0.1:8000/draft/state')
    const data = await res.json()
    setDraftState(data)
  }

  const makeNextPick = async () => {
    setLoadingPick(true)
    await fetch('http://127.0.0.1:8000/draft/next-pick', { method: 'POST' })
    await fetchDraftState()
    setLoadingPick(false)
  }

  const resetDraft = async () => {
    await fetch('http://127.0.0.1:8000/draft/reset', { method: 'POST' })
    await fetchDraftState()
  }

  const pickPlayer = async (playerName) => {
    await fetch('http://127.0.0.1:8000/draft/pick-player', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player_name: playerName })
    })
    await fetchDraftState()
  }

  useEffect(() => {
    fetchDraftState()
  }, [])

  if (!draftState) return <div>Loading...</div>

  return (
    <div className="container">
      <h1>🏈 Fantasy Draft Board</h1>

      <div className="controls">
        <button onClick={makeNextPick} disabled={loadingPick}>
          {loadingPick ? 'Picking...' : 'Auto Pick Best Player'}
        </button>
        <button onClick={resetDraft}>Reset Draft</button>
      </div>

      <div className="layout">
        {/* Left Panel - Draft Picks */}
        <div className="draft-picks">
          <h2>Draft Picks</h2>
          <div className="pick-list">
            {[...Array(48)].map((_, i) => {
              const pick = draftState.picks.find(p => p.pick_number === i + 1)
              return (
                <div className="pick" key={i}>
                  {i + 1}. {pick ? `${pick.username} - ${pick.player}` : "EMPTY"}
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Panel - Available Players */}
        <div className="available-players">
          <h2>Available Players</h2>
          <ul>
            {draftState.available_players
              .filter(p => !p.pick_taken)
              .slice(0, 20)
              .map((player, idx) => (
                <li key={idx}>
                  {player.player_name} ({player.position})
                  <button onClick={() => pickPlayer(player.player_name)}>Pick</button>
                </li>
              ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export default App
