/* PointChess Ensemble — browser application */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────

const S = {
  fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  turn: 'white',
  legal: [],
  status: 'ongoing',
  humanColor: 'white',
  elo: 1500,
  method: 'plurality',
  history: [],
  inCheck: false,
  fullmove: 1,

  // Selection state
  selected: null,       // algebraic square string e.g. "e2"
  pendingPromo: null,   // {from, to} waiting for promo choice
  lastFrom: null,
  lastTo: null,

  engineThinking: false,
};

// ── Unicode pieces ─────────────────────────────────────────────────────────

const PIECES = {
  K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘', P: '♙',
  k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟',
};

// ── Helpers ────────────────────────────────────────────────────────────────

function sq(file, rank) {   // file 0-7, rank 0-7 → "a1".."h8"
  return String.fromCharCode(97 + file) + (rank + 1);
}

function fromAlg(alg) {     // "e2" → {file, rank}
  return { file: alg.charCodeAt(0) - 97, rank: parseInt(alg[1]) - 1 };
}

function fenToBoard(fen) {
  const board = [];
  const rows = fen.split(' ')[0].split('/');
  for (let r = 7; r >= 0; r--) {
    const row = [];
    for (const ch of rows[7 - r]) {
      if (/\d/.test(ch)) { for (let i = 0; i < +ch; i++) row.push(null); }
      else row.push(ch);
    }
    board.push(row);  // board[rank][file]
  }
  return board;
}

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

// ── Board rendering ────────────────────────────────────────────────────────

function renderBoard() {
  const el = document.getElementById('board');
  el.innerHTML = '';
  const board = fenToBoard(S.fen);
  const flip = S.humanColor === 'black';

  const ranks = flip ? [0,1,2,3,4,5,6,7] : [7,6,5,4,3,2,1,0];
  const files = flip ? [7,6,5,4,3,2,1,0] : [0,1,2,3,4,5,6,7];

  const legalDests = new Set(S.legal.map(m => m.slice(2, 4)));
  const legalFrom  = new Set(S.legal.map(m => m.slice(0, 2)));

  for (const rank of ranks) {
    for (const file of files) {
      const sqStr = sq(file, rank);
      const div = document.createElement('div');
      div.className = 'sq ' + ((file + rank) % 2 === 0 ? 'dark' : 'light');
      div.dataset.sq = sqStr;

      // Last-move highlight
      if (sqStr === S.lastFrom || sqStr === S.lastTo) {
        div.classList.add('last-move');
      }

      // In-check king highlight
      const piece = board[rank][file];
      const kingColor = S.turn === 'white' ? 'K' : 'k';
      if (S.inCheck && piece === kingColor) {
        div.classList.add('in-check');
      }

      // Piece
      if (piece) {
        div.textContent = PIECES[piece] || '';
      }

      // Selected square
      if (sqStr === S.selected) {
        div.classList.add('selected');
      }

      // Legal move overlays
      if (S.selected) {
        const moves = S.legal.filter(m => m.slice(0,2) === S.selected && m.slice(2,4) === sqStr);
        if (moves.length) {
          if (piece) {
            const ring = document.createElement('div');
            ring.className = 'ring';
            div.appendChild(ring);
          } else {
            const dot = document.createElement('div');
            dot.className = 'dot';
            div.appendChild(dot);
          }
        }
      }

      div.addEventListener('click', () => onSquareClick(sqStr));
      el.appendChild(div);
    }
  }
}

// ── Move handling ──────────────────────────────────────────────────────────

function onSquareClick(sqStr) {
  if (S.engineThinking) return;
  if (S.status !== 'ongoing') return;
  if (S.turn !== S.humanColor) return;

  if (S.selected) {
    const legalForSrc = S.legal.filter(m => m.slice(0,2) === S.selected && m.slice(2,4) === sqStr);
    if (legalForSrc.length) {
      // Check if promotion
      if (legalForSrc.some(m => m.length === 5)) {
        S.pendingPromo = { from: S.selected, to: sqStr };
        document.getElementById('promotion-modal').classList.remove('hidden');
        S.selected = null;
        return;
      }
      sendMove(S.selected + sqStr);
      return;
    }
    S.selected = null;
  }

  // Select a piece if it belongs to the human
  const hasMoves = S.legal.some(m => m.slice(0,2) === sqStr);
  S.selected = hasMoves ? sqStr : null;
  renderBoard();
}

async function promote(piece) {
  document.getElementById('promotion-modal').classList.add('hidden');
  if (!S.pendingPromo) return;
  const uci = S.pendingPromo.from + S.pendingPromo.to + piece;
  S.pendingPromo = null;
  await sendMove(uci);
}

async function sendMove(uci) {
  S.selected = null;
  const data = await api('POST', '/api/move', { move: uci });
  if (!data.ok) {
    setStatus('Illegal move: ' + uci);
    return;
  }
  S.lastFrom = uci.slice(0, 2);
  S.lastTo   = uci.slice(2, 4);
  updateFromState(data.state);

  // Trigger engine move if game still ongoing and it's engine's turn
  if (S.status === 'ongoing' && S.turn !== S.humanColor) {
    await triggerEngineMove();
  }
}

async function triggerEngineMove() {
  S.engineThinking = true;
  showThinking(true);
  renderBoard();

  const data = await api('GET', '/api/engine');
  S.engineThinking = false;
  showThinking(false);

  if (data.ok) {
    const em = data.ensemble;
    const move = em.chosen_move;
    S.lastFrom = move.slice(0, 2);
    S.lastTo   = move.slice(2, 4);
    updateEnsemblePanel(em);
  }
  await refreshState();
}

// ── State updates ──────────────────────────────────────────────────────────

function updateFromState(state) {
  S.fen = state.fen;
  S.turn = state.turn;
  S.legal = state.legal_moves;
  S.status = state.status;
  S.inCheck = state.in_check;
  S.fullmove = state.fullmove;
  S.history = state.move_history;
  renderBoard();
  renderMoveList();
  updateStatusBar();
}

async function refreshState() {
  const state = await api('GET', '/api/state');
  updateFromState(state);
}

function setStatus(msg) {
  document.getElementById('status-bar').textContent = msg;
}

function updateStatusBar() {
  const msgs = {
    checkmate: `Checkmate — ${S.turn === 'white' ? 'Black' : 'White'} wins!`,
    stalemate: 'Stalemate — Draw',
    draw: 'Draw',
    resigned: 'Resigned',
    ongoing: S.inCheck
      ? `${S.turn === 'white' ? 'White' : 'Black'} is in check!`
      : `${S.turn === 'white' ? 'White' : 'Black'} to move`,
  };
  setStatus(msgs[S.status] || '');
}

function renderMoveList() {
  const el = document.getElementById('move-list');
  el.innerHTML = '';
  let num = 1;
  const items = S.history;
  for (let i = 0; i < items.length; i++) {
    const { by, move } = items[i];
    const span = document.createElement('span');
    span.className = by === 'engine' ? 'engine-move' : 'human-move';

    if (by === 'human' && (i === 0 || items[i-1].by === 'engine')) {
      const label = document.createElement('span');
      label.style.color = '#556';
      label.textContent = `${num}. `;
      el.appendChild(label);
      num++;
    }
    span.textContent = move + ' ';
    el.appendChild(span);
  }
  el.scrollTop = el.scrollHeight;
}

// ── Ensemble panel ─────────────────────────────────────────────────────────

function showThinking(show) {
  document.getElementById('thinking-indicator').classList.toggle('hidden', !show);
  if (show) {
    document.getElementById('vote-results').innerHTML = '';
    document.getElementById('candidates').innerHTML = '';
  }
}

function updateEnsemblePanel(em) {
  // Vote cards
  const vr = document.getElementById('vote-results');
  vr.innerHTML = '';
  for (const v of em.votes) {
    const card = document.createElement('div');
    if (!v.success) {
      card.className = 'vote-card failed';
      card.innerHTML = `<span class="vote-llm">${v.llm}</span><span>Error</span><span class="vote-ms">${v.latency_ms}ms</span>`;
    } else {
      const isWinner = v.move === em.chosen_move;
      card.className = 'vote-card ' + (isWinner ? 'winner' : 'loser');
      card.innerHTML = `<span class="vote-llm">${v.llm}</span><span class="vote-move">${v.move}</span><span class="vote-ms">${v.latency_ms}ms</span>`;
    }
    vr.appendChild(card);
  }

  // Fallback / blunder notices
  if (em.fallback_used) {
    const note = document.createElement('div');
    note.className = 'fallback-note';
    note.textContent = '⚠ Fallback: ' + em.fallback_reason;
    vr.appendChild(note);
  }
  if (em.blunder_applied) {
    const note = document.createElement('div');
    note.className = 'blunder-note';
    note.textContent = '⚡ ELO-scaled blunder applied';
    vr.appendChild(note);
  }

  // Candidate bars
  const cc = document.getElementById('candidates');
  cc.innerHTML = '';
  const maxVotes = Math.max(1, ...Object.values(em.vote_counts));
  for (let i = 0; i < em.candidates.length; i++) {
    const mv = em.candidates[i];
    const votes = em.vote_counts[mv] || 0;
    const isTop = mv === em.chosen_move;
    const pct = Math.round((votes / maxVotes) * 100);

    const row = document.createElement('div');
    row.className = 'cand-row';
    row.innerHTML = `
      <span class="cand-move">${mv}</span>
      <div class="cand-bar-wrap"><div class="cand-bar${isTop?' top':''}" style="width:${pct}%"></div></div>
      <span class="cand-votes">${votes}v</span>`;
    cc.appendChild(row);
  }

  // Stats
  document.getElementById('stat-depth').textContent = em.ab_depth;
  document.getElementById('stat-nodes').textContent = em.ab_nodes.toLocaleString();
  document.getElementById('stat-score').textContent = em.ab_score_cp + ' cp';
  document.getElementById('stat-time').textContent = em.ab_elapsed_ms + ' ms';
  document.getElementById('stat-elo').textContent = em.elo;
  document.getElementById('stat-method').textContent = em.voting_method;
}

// ── Controls ───────────────────────────────────────────────────────────────

function setSide(color) {
  S.humanColor = color;
  document.getElementById('btn-white').classList.toggle('active', color === 'white');
  document.getElementById('btn-black').classList.toggle('active', color === 'black');
  newGame();
}

async function newGame() {
  await api('POST', '/api/new', { human_color: S.humanColor });
  S.lastFrom = null;
  S.lastTo = null;
  S.selected = null;
  document.getElementById('vote-results').innerHTML = '<p class="placeholder">Engine vote results will appear here after each engine move.</p>';
  document.getElementById('candidates').innerHTML = '';
  document.getElementById('stat-depth').textContent = '—';
  document.getElementById('stat-nodes').textContent = '—';
  document.getElementById('stat-score').textContent = '—';
  document.getElementById('stat-time').textContent = '—';
  document.getElementById('stat-elo').textContent = S.elo;
  document.getElementById('stat-method').textContent = S.method;
  await refreshState();

  // If human plays Black, engine moves first
  if (S.humanColor === 'black' && S.turn === 'white') {
    await triggerEngineMove();
  }
}

async function undoMove() {
  if (S.engineThinking) return;
  await api('POST', '/api/undo');
  S.lastFrom = null;
  S.lastTo = null;
  S.selected = null;
  await refreshState();
}

async function resign() {
  if (S.engineThinking) return;
  await api('POST', '/api/resign');
  await refreshState();
}

function updateElo(val) {
  S.elo = parseInt(val);
  document.getElementById('elo-display').textContent = val;
  api('POST', '/api/option', { elo: S.elo });
}

function updateMethod(val) {
  S.method = val;
  api('POST', '/api/option', { method: val });
}

// ── Boot ───────────────────────────────────────────────────────────────────

(async () => {
  await refreshState();
})();
