// Minimal chess UI: parses FEN, renders 8x8 grid, handles click-to-move.

const PIECE_GLYPHS = {
  P: '♙', N: '♘', B: '♗', R: '♖', Q: '♕', K: '♔',
  p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚',
};

const FILES = ['a','b','c','d','e','f','g','h'];
const boardEl   = document.getElementById('board');
const statusEl  = document.getElementById('status');
const fenEl     = document.getElementById('fen');
const historyEl = document.getElementById('history');
const lastEl    = document.getElementById('last-engine');
const eloIn     = document.getElementById('elo');
const eloOut    = document.getElementById('elo-out');
const sideSel   = document.getElementById('side');
const promoEl   = document.getElementById('promo');

let state = null;
let selected = null;        // square name like "e2"
let legalForSelected = [];  // list of UCI moves starting at `selected`
let pendingPromotion = null; // {from, to}

eloIn.addEventListener('input', () => { eloOut.textContent = eloIn.value; });

document.getElementById('new-game').onclick = async () => {
  const r = await fetch('/api/new_game', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ side: sideSel.value, elo: parseInt(eloIn.value, 10) }),
  });
  state = await r.json();
  selected = null; legalForSelected = []; pendingPromotion = null;
  promoEl.classList.add('hidden');
  render();
};

document.getElementById('resign').onclick = async () => {
  if (!state) return;
  const r = await fetch('/api/resign', { method: 'POST' });
  state = await r.json();
  render();
};

promoEl.querySelectorAll('button').forEach(btn => {
  btn.onclick = async () => {
    if (!pendingPromotion) return;
    const piece = btn.dataset.piece;
    const uci = pendingPromotion.from + pendingPromotion.to + piece;
    pendingPromotion = null;
    promoEl.classList.add('hidden');
    await sendMove(uci);
  };
});

// ----- rendering ------------------------------------------------------

function parseFen(fen) {
  // Returns an 8x8 array of piece chars (or '.') indexed [rank][file]
  // with rank 0 = rank 8 (top of board from white's POV).
  const placement = fen.split(' ')[0];
  const ranks = placement.split('/');
  const grid = [];
  for (const r of ranks) {
    const row = [];
    for (const ch of r) {
      if (/\d/.test(ch)) {
        for (let i = 0; i < parseInt(ch, 10); i++) row.push('.');
      } else {
        row.push(ch);
      }
    }
    grid.push(row);
  }
  return grid;
}

function squareName(file, rank) { return FILES[file] + (rank + 1); }

function render() {
  if (!state) return;
  const grid = parseFen(state.fen);
  const flip = (state.human_color === 'black');

  const lastFrom = state.last_move_uci ? state.last_move_uci.slice(0, 2) : null;
  const lastTo   = state.last_move_uci ? state.last_move_uci.slice(2, 4) : null;

  boardEl.innerHTML = '';

  // visualRanks: 0..7 from top to bottom of the rendered board.
  for (let visR = 0; visR < 8; visR++) {
    for (let visF = 0; visF < 8; visF++) {
      const rank = flip ? visR : 7 - visR;       // 0..7 (rank 1..8)
      const file = flip ? 7 - visF : visF;       // 0..7 (file a..h)
      const sq = squareName(file, rank);

      const cell = document.createElement('div');
      cell.className = 'sq ' + (((file + rank) % 2 === 0) ? 'dark' : 'light');
      cell.dataset.square = sq;

      // grid is indexed with rank 8 at row 0, so:
      const piece = grid[7 - rank][file];
      if (piece !== '.') {
        const span = document.createElement('span');
        span.className = 'piece ' + (piece === piece.toUpperCase() ? 'white' : 'black');
        span.textContent = PIECE_GLYPHS[piece];
        cell.appendChild(span);
      }

      // Highlights.
      if (selected === sq) cell.classList.add('selected');
      if (sq === lastFrom || sq === lastTo) cell.classList.add('last-move');
      if (state.in_check && piece && piece.toLowerCase() === 'k'
          && ((piece === 'K' && state.turn === 'white')
           || (piece === 'k' && state.turn === 'black'))) {
        cell.classList.add('in-check');
      }

      // Legal-move dot for the currently selected piece.
      if (selected && legalForSelected.some(u => u.startsWith(sq.length === 2 ? selected : ''))) {
        for (const uci of legalForSelected) {
          if (uci.slice(2, 4) === sq) {
            const dot = document.createElement('div');
            dot.className = 'legal-dot';
            cell.appendChild(dot);
            const occ = piece !== '.';
            if (occ) cell.classList.add('is-capture');
            break;
          }
        }
      }

      cell.addEventListener('click', () => onSquareClick(sq));
      boardEl.appendChild(cell);
    }
  }

  statusEl.textContent = state.status;
  fenEl.textContent = state.fen;
  lastEl.textContent = state.last_engine_san
    ? `${state.last_engine_san}  (${state.last_engine_uci})`
    : '—';

  historyEl.innerHTML = '';
  for (let i = 0; i < state.history_san.length; i += 2) {
    const li = document.createElement('li');
    const w = state.history_san[i] || '';
    const b = state.history_san[i + 1] || '';
    li.textContent = `${w}  ${b}`;
    historyEl.appendChild(li);
  }

  eloOut.textContent = state.elo;
  eloIn.value = state.elo;
}

// ----- click-to-move -------------------------------------------------

async function onSquareClick(sq) {
  if (!state || state.is_over) return;
  if (state.turn !== state.human_color) return;

  if (selected === null) {
    // Try to select this square if it has one of our legal moves.
    const r = await fetch('/api/legal_moves?from=' + sq);
    const data = await r.json();
    if (data.moves && data.moves.length > 0) {
      selected = sq;
      legalForSelected = data.moves;
      render();
    }
    return;
  }

  if (sq === selected) {
    selected = null; legalForSelected = []; render();
    return;
  }

  // Find a matching legal move.
  const candidates = legalForSelected.filter(u => u.slice(2, 4) === sq);
  if (candidates.length === 0) {
    // Maybe user is reselecting. Try to select the new square.
    selected = null; legalForSelected = [];
    onSquareClick(sq);
    return;
  }

  // Promotion?
  if (candidates.some(u => u.length === 5)) {
    pendingPromotion = { from: selected, to: sq };
    selected = null; legalForSelected = [];
    promoEl.classList.remove('hidden');
    render();
    return;
  }

  await sendMove(candidates[0]);
}

async function sendMove(uci) {
  selected = null; legalForSelected = [];
  const r = await fetch('/api/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ uci }),
  });
  state = await r.json();
  render();
}

// Initial load: fetch state if a game already exists in the server's memory.
(async () => {
  const r = await fetch('/api/state');
  state = await r.json();
  render();
})();
