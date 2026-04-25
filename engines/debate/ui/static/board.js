// Vanilla JS chess UI talking to the Python engine via /api/*.
// No frameworks.

const PIECE_GLYPH = {
  P: "\u2659", N: "\u2658", B: "\u2657", R: "\u2656", Q: "\u2655", K: "\u2654",
  p: "\u265F", n: "\u265E", b: "\u265D", r: "\u265C", q: "\u265B", k: "\u265A",
};

const FILES = "abcdefgh";

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const eloEl = document.getElementById("elo");
const eloVal = document.getElementById("elo-val");
const limitEl = document.getElementById("limit-strength");
const movetimeEl = document.getElementById("movetime");
const depthEl = document.getElementById("depth");
const scoreEl = document.getElementById("score");
const pvEl = document.getElementById("pv");
const lastEl = document.getElementById("last");
const resultEl = document.getElementById("result");

let state = null;
let selected = null;   // square id like "e2"
let legalFromSelected = [];

// --- Rendering -----------------------------------------------------------

function fenToBoard(fen) {
  const rows = fen.split(" ")[0].split("/");
  // rows[0] is rank 8
  const board = {};
  for (let i = 0; i < 8; i++) {
    const rank = 8 - i;
    let f = 0;
    for (const c of rows[i]) {
      if (/\d/.test(c)) {
        f += parseInt(c, 10);
      } else {
        const sq = FILES[f] + rank;
        board[sq] = c;
        f++;
      }
    }
  }
  return board;
}

function render() {
  boardEl.innerHTML = "";
  if (!state) return;
  const board = fenToBoard(state.fen);
  const checkSq = state.in_check ? findKingSq(board, state.turn) : null;

  // Build squares from rank 8 down to rank 1, files a..h
  for (let r = 8; r >= 1; r--) {
    for (let fi = 0; fi < 8; fi++) {
      const f = FILES[fi];
      const id = f + r;
      const div = document.createElement("div");
      div.className = "sq " + (((fi + r) % 2 === 0) ? "dark" : "light");
      div.dataset.sq = id;
      const piece = board[id];
      if (piece) div.textContent = PIECE_GLYPH[piece] || "";
      if (selected === id) div.classList.add("sel");
      if (legalFromSelected.includes(id)) {
        div.classList.add("target");
        if (piece) div.classList.add("capture");
      }
      if (checkSq === id) div.classList.add("check");
      // file/rank labels on edges
      if (r === 1) {
        const c = document.createElement("span");
        c.className = "coord file"; c.textContent = f;
        div.appendChild(c);
      }
      if (fi === 0) {
        const c = document.createElement("span");
        c.className = "coord rank"; c.textContent = r;
        div.appendChild(c);
      }
      div.addEventListener("click", () => onSquareClick(id));
      boardEl.appendChild(div);
    }
  }

  statusEl.textContent =
    state.game_over ? `game over: ${state.result}` :
    (state.turn + " to move" + (state.in_check ? " (check)" : ""));
  depthEl.textContent = state.depth || "-";
  scoreEl.textContent = state.score_cp;
  pvEl.textContent = (state.pv && state.pv.length) ? state.pv.join(" ") : "-";
  lastEl.textContent = state.last_bestmove || "-";
  resultEl.textContent = state.game_over ? state.result : "in progress";
}

function findKingSq(board, turn) {
  const target = (turn === "white") ? "K" : "k";
  for (const [sq, p] of Object.entries(board)) {
    if (p === target) return sq;
  }
  return null;
}

// --- Interaction ---------------------------------------------------------

async function onSquareClick(sq) {
  if (!state || state.game_over) return;
  if (state.search_active) return;
  if (selected === null) {
    // try to select a piece of the side-to-move
    if (legalMovesFrom(sq).length > 0) {
      selected = sq;
      legalFromSelected = legalMovesFrom(sq).map(m => m.slice(2, 4));
      render();
    }
    return;
  }
  if (selected === sq) {
    selected = null; legalFromSelected = []; render(); return;
  }
  // try to move selected -> sq
  const candidates = (state.legal_moves || []).filter(
    m => m.startsWith(selected) && m.slice(2, 4) === sq
  );
  if (candidates.length === 0) {
    // re-select if clicking another own piece
    if (legalMovesFrom(sq).length > 0) {
      selected = sq;
      legalFromSelected = legalMovesFrom(sq).map(m => m.slice(2, 4));
      render();
    } else {
      selected = null; legalFromSelected = []; render();
    }
    return;
  }
  // Pick promotion
  let move = candidates[0];
  if (move.length === 5) {
    const choice = (prompt("Promote to (q/r/b/n)?", "q") || "q").toLowerCase();
    const found = candidates.find(m => m.endsWith(choice));
    move = found || move;
  }
  selected = null; legalFromSelected = [];
  await postJSON("/api/move", { uci: move });
  await refreshState();
  // If game continues and it's engine's turn, trigger engine think.
  if (!state.game_over) {
    await postJSON("/api/go", { movetime: parseInt(movetimeEl.value, 10) });
  }
}

function legalMovesFrom(sq) {
  if (!state) return [];
  return (state.legal_moves || []).filter(m => m.startsWith(sq));
}

// --- API plumbing --------------------------------------------------------

async function refreshState() {
  const r = await fetch("/api/state");
  state = await r.json();
  render();
}

async function postJSON(url, body) {
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

// Buttons
document.getElementById("btn-new").addEventListener("click", async () => {
  await postJSON("/api/newgame", {});
  selected = null; legalFromSelected = [];
  await refreshState();
});
document.getElementById("btn-engine-move").addEventListener("click", async () => {
  await postJSON("/api/go", { movetime: parseInt(movetimeEl.value, 10) });
});
document.getElementById("btn-stop").addEventListener("click", async () => {
  await postJSON("/api/stop", {});
});

eloEl.addEventListener("input", () => { eloVal.textContent = eloEl.value; });
eloEl.addEventListener("change", async () => {
  await postJSON("/api/elo", { elo: parseInt(eloEl.value, 10),
                               limit: limitEl.checked });
});
limitEl.addEventListener("change", async () => {
  await postJSON("/api/elo", { elo: parseInt(eloEl.value, 10),
                               limit: limitEl.checked });
});

// poll
async function poll() {
  try { await refreshState(); } catch (e) {}
  setTimeout(poll, 400);
}

(async () => {
  await postJSON("/api/elo", { elo: parseInt(eloEl.value, 10),
                               limit: limitEl.checked });
  await refreshState();
  poll();
})();
