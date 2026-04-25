// PyChess vanilla-JS UI.
const PIECE = {
  P:"\u2659", N:"\u2658", B:"\u2657", R:"\u2656", Q:"\u2655", K:"\u2654",
  p:"\u265F", n:"\u265E", b:"\u265D", r:"\u265C", q:"\u265B", k:"\u265A",
};
const FILES = "abcdefgh";

let state = null;
let selected = null;
let humanColor = "w";
let pollTimer = null;

function fenToGrid(fen) {
  const rows = fen.split(" ")[0].split("/");
  const grid = [];
  for (const row of rows) {
    const r = [];
    for (const ch of row) {
      if (/[1-8]/.test(ch)) {
        for (let i = 0; i < +ch; i++) r.push(null);
      } else r.push(ch);
    }
    grid.push(r);
  }
  return grid;
}

function squareName(file, rankFromTop) {
  return FILES[file] + (8 - rankFromTop);
}

function render() {
  const board = document.getElementById("board");
  board.innerHTML = "";
  if (!state) return;
  const grid = fenToGrid(state.fen);
  const flip = humanColor === "b";
  for (let r = 0; r < 8; r++) {
    for (let f = 0; f < 8; f++) {
      const rr = flip ? 7 - r : r;
      const ff = flip ? 7 - f : f;
      const sq = document.createElement("div");
      sq.className = "sq " + ((r + f) % 2 === 0 ? "light" : "dark");
      const name = squareName(ff, rr);
      sq.dataset.sq = name;
      const piece = grid[rr][ff];
      if (piece) sq.textContent = PIECE[piece];
      if (selected === name) sq.classList.add("selected");
      if (selected) {
        const moves = (state.legal_moves || []).filter(m => m.startsWith(selected));
        if (moves.some(m => m.substring(2,4) === name)) sq.classList.add("target");
      }
      sq.addEventListener("click", () => onClick(name));
      board.appendChild(sq);
    }
  }
  document.getElementById("status").textContent =
    state.status === "ongoing"
      ? (state.side_to_move === "w" ? "White to move" : "Black to move")
        + (state.thinking ? " — engine thinking..." : "")
      : "Game over: " + state.status;
}

async function refresh() {
  const r = await fetch("/state");
  state = await r.json();
  render();
  if (state.thinking) {
    if (!pollTimer) pollTimer = setInterval(refresh, 300);
  } else {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }
}

async function onClick(name) {
  if (!state || state.status !== "ongoing") return;
  if (state.side_to_move !== humanColor) return;
  if (selected === null) {
    // Must select a piece of own color.
    const grid = fenToGrid(state.fen);
    const f = FILES.indexOf(name[0]); const r = 8 - +name[1];
    const piece = grid[r][f];
    if (!piece) return;
    if (humanColor === "w" && piece === piece.toLowerCase()) return;
    if (humanColor === "b" && piece === piece.toUpperCase()) return;
    selected = name;
    render();
    return;
  }
  if (selected === name) { selected = null; render(); return; }
  // Try to make move selected -> name (auto-promote to queen).
  let from = selected;
  selected = null;
  let candidates = (state.legal_moves || []).filter(m => m.startsWith(from) && m.substring(2,4) === name);
  if (candidates.length === 0) {
    // Maybe selected another own piece? re-select.
    const grid = fenToGrid(state.fen);
    const f = FILES.indexOf(name[0]); const r = 8 - +name[1];
    const piece = grid[r][f];
    if (piece && ((humanColor === "w" && piece === piece.toUpperCase()) ||
                  (humanColor === "b" && piece === piece.toLowerCase()))) {
      selected = name;
    }
    render();
    return;
  }
  // Prefer promotion to queen.
  let move = candidates.find(m => m.length === 5 && m.endsWith("q")) || candidates[0];
  await fetch("/move", { method: "POST", headers: {"Content-Type":"application/json"},
                         body: JSON.stringify({move}) });
  await refresh();
}

document.getElementById("newgame").addEventListener("click", async () => {
  humanColor = document.getElementById("color").value;
  const elo = +document.getElementById("elo").value;
  await fetch("/new", { method: "POST", headers: {"Content-Type":"application/json"},
                        body: JSON.stringify({elo, human_color: humanColor}) });
  selected = null;
  await refresh();
});
document.getElementById("stop").addEventListener("click", async () => {
  await fetch("/stop", { method: "POST" });
  await refresh();
});
document.getElementById("elo").addEventListener("input", e => {
  document.getElementById("elo-val").textContent = e.target.value;
});

refresh();
setInterval(refresh, 1500);
