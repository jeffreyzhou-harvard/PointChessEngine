"use strict";

const PIECE_SYMBOLS = {
  P: "\u2659", N: "\u2658", B: "\u2657", R: "\u2656", Q: "\u2655", K: "\u2654",
  p: "\u265F", n: "\u265E", b: "\u265D", r: "\u265C", q: "\u265B", k: "\u265A",
};

const FILES = ["a","b","c","d","e","f","g","h"];

const boardEl = document.getElementById("board");
const statusEl = document.getElementById("status");
const moveListEl = document.getElementById("move-list");
const engineInfoEl = document.getElementById("engine-info");
const eloSlider = document.getElementById("elo-slider");
const eloValueEl = document.getElementById("elo-value");
const sideSelect = document.getElementById("side-select");
const promotionModal = document.getElementById("promotion-modal");

let state = null;
let selectedFrom = null;
let pendingPromotion = null;       // { from, to } awaiting promotion choice
let lastMoveSquares = null;        // [from, to] for highlight

function algebraic(row, col, flipped) {
  const r = flipped ? row : (7 - row);
  const c = flipped ? (7 - col) : col;
  return FILES[c] + (r + 1);
}

function isHumanFlipped() {
  return state && state.human_color === "b";
}

function render() {
  if (!state) return;
  const flipped = isHumanFlipped();
  boardEl.innerHTML = "";

  // We always iterate display rows 0..7 from the human's top-down.
  // displayRow=0 is the top of the visible board.
  for (let displayRow = 0; displayRow < 8; displayRow++) {
    for (let displayCol = 0; displayCol < 8; displayCol++) {
      // Map display coords -> board indexing (row 0 = rank 8 in board.squares)
      const boardRow = flipped ? (7 - displayRow) : displayRow;
      const boardCol = flipped ? (7 - displayCol) : displayCol;
      const sq = document.createElement("div");
      const isLight = (boardRow + boardCol) % 2 === 0;
      sq.className = "square " + (isLight ? "light" : "dark");
      const algeb = FILES[boardCol] + (8 - boardRow);
      sq.dataset.square = algeb;

      // file/rank coordinates on edges
      if (displayRow === 7) {
        const f = document.createElement("span");
        f.className = "coord file";
        f.textContent = FILES[boardCol];
        sq.appendChild(f);
      }
      if (displayCol === 0) {
        const r = document.createElement("span");
        r.className = "coord rank";
        r.textContent = String(8 - boardRow);
        sq.appendChild(r);
      }

      const pieceChar = state.squares[boardRow][boardCol];
      if (pieceChar) {
        const span = document.createElement("span");
        span.className = "piece";
        span.textContent = PIECE_SYMBOLS[pieceChar] || "?";
        sq.appendChild(span);
        sq.classList.add("has-piece");
      }

      if (lastMoveSquares && (lastMoveSquares[0] === algeb || lastMoveSquares[1] === algeb)) {
        sq.classList.add("last-move");
      }

      if (selectedFrom === algeb) sq.classList.add("selected");

      // Legal-move overlays (only for human's selection)
      if (selectedFrom && state.legal_moves_by_from[selectedFrom]) {
        for (const uci of state.legal_moves_by_from[selectedFrom]) {
          if (uci.slice(2, 4) === algeb) {
            const dot = document.createElement("span");
            dot.className = "legal-dot";
            sq.appendChild(dot);
          }
        }
      }

      // Check highlight: highlight king of side to move
      if (state.in_check && pieceChar) {
        const kingChar = state.turn === "w" ? "K" : "k";
        if (pieceChar === kingChar) sq.classList.add("in-check");
      }

      sq.addEventListener("click", () => onSquareClick(algeb));
      boardEl.appendChild(sq);
    }
  }

  // Status text
  if (state.game_over) {
    statusEl.textContent = `${state.result_reason} (${state.result})`;
  } else {
    const turn = state.turn === "w" ? "White" : "Black";
    const human = state.human_color === "w" ? "White" : "Black";
    const youOrEngine = (state.turn === state.human_color) ? "Your move" : "Engine thinking…";
    statusEl.textContent = `${turn} to move — ${youOrEngine} (you: ${human})`;
  }

  renderMoveList();
  renderEngineInfo();
}

function renderMoveList() {
  moveListEl.innerHTML = "";
  for (let i = 0; i < state.move_log.length; i += 2) {
    const li = document.createElement("li");
    const w = state.move_log[i];
    const b = state.move_log[i + 1];
    let txt = `${w.san}`;
    if (w.by === "engine") txt = `<span class="by-engine">${w.san}</span>`;
    if (b) {
      const bTxt = b.by === "engine" ? `<span class="by-engine">${b.san}</span>` : b.san;
      txt += "  " + bTxt;
    }
    li.innerHTML = txt;
    moveListEl.appendChild(li);
  }
  moveListEl.scrollTop = moveListEl.scrollHeight;
}

function renderEngineInfo() {
  if (!state.last_engine || !state.last_engine.played_uci) {
    engineInfoEl.innerHTML = '<p class="muted">No engine moves yet.</p>';
    return;
  }
  const e = state.last_engine;
  const score = (e.score_cp / 100).toFixed(2);
  let html = `
    <div class="stat"><span>Played</span><span>${e.played_uci}</span></div>
    <div class="stat"><span>Best</span><span>${e.best_uci || "?"}</span></div>
    <div class="stat"><span>Eval</span><span>${score}</span></div>
    <div class="stat"><span>Depth</span><span>${e.depth}</span></div>
    <div class="stat"><span>Nodes</span><span>${e.nodes.toLocaleString()}</span></div>
    <div class="stat"><span>Time</span><span>${e.elapsed_ms} ms</span></div>
    <div class="stat"><span>PV</span><span>${(e.pv || []).join(" ")}</span></div>
  `;
  if (e.reasoning) {
    html += `<div class="reasoning">${e.reasoning.replace(/</g, "&lt;")}</div>`;
  }
  engineInfoEl.innerHTML = html;
}

async function onSquareClick(square) {
  if (!state || state.game_over) return;
  if (state.turn !== state.human_color) return;

  // If we already selected a piece, treat this as the destination
  if (selectedFrom) {
    if (selectedFrom === square) {
      selectedFrom = null;
      render();
      return;
    }
    const candidates = (state.legal_moves_by_from[selectedFrom] || [])
      .filter((u) => u.slice(2, 4) === square);
    if (candidates.length > 0) {
      // Promotion?
      const promotions = candidates.filter((u) => u.length === 5);
      if (promotions.length > 0) {
        pendingPromotion = { from: selectedFrom, to: square };
        showPromotion();
        return;
      }
      await sendMove(candidates[0]);
      return;
    }
    // else: maybe selecting a different piece
    if (state.legal_moves_by_from[square]) {
      selectedFrom = square;
      render();
      return;
    }
    selectedFrom = null;
    render();
    return;
  }

  if (state.legal_moves_by_from[square]) {
    selectedFrom = square;
    render();
  }
}

function showPromotion() {
  promotionModal.classList.remove("hidden");
}

document.querySelectorAll("#promotion-modal [data-promo]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!pendingPromotion) return;
    const promo = btn.dataset.promo;
    const uci = pendingPromotion.from + pendingPromotion.to + promo;
    pendingPromotion = null;
    promotionModal.classList.add("hidden");
    await sendMove(uci);
  });
});

async function sendMove(uci) {
  selectedFrom = null;
  const res = await fetch("/api/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uci }),
  });
  const json = await res.json();
  if (!json.ok) {
    statusEl.textContent = "Illegal move: " + (json.error || "");
    return;
  }
  lastMoveSquares = [uci.slice(0, 2), uci.slice(2, 4)];
  state = json.state;
  render();
  await maybeEngineMove();
}

async function maybeEngineMove() {
  if (state.game_over) return;
  if (state.turn === state.human_color) return;
  // Engine plays
  statusEl.textContent = "Engine thinking…";
  const res = await fetch("/api/engine_move", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const json = await res.json();
  if (json.ok) {
    lastMoveSquares = [json.move.slice(0, 2), json.move.slice(2, 4)];
  }
  state = json.state || state;
  render();
}

async function refreshState() {
  const res = await fetch("/api/state");
  state = await res.json();
  eloSlider.value = state.elo;
  eloValueEl.textContent = state.elo;
  sideSelect.value = state.human_color;
  render();
}

document.getElementById("new-game").addEventListener("click", async () => {
  const res = await fetch("/api/new_game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ human_color: sideSelect.value }),
  });
  state = await res.json();
  selectedFrom = null;
  lastMoveSquares = null;
  render();
  await maybeEngineMove();
});

document.getElementById("undo-btn").addEventListener("click", async () => {
  const res = await fetch("/api/undo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const json = await res.json();
  state = json.state;
  selectedFrom = null;
  lastMoveSquares = null;
  render();
});

document.getElementById("resign-btn").addEventListener("click", async () => {
  if (!confirm("Resign the current game?")) return;
  const res = await fetch("/api/resign", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const json = await res.json();
  state = json.state;
  render();
});

document.getElementById("pgn-btn").addEventListener("click", async () => {
  const res = await fetch("/api/pgn");
  const json = await res.json();
  const blob = new Blob([json.pgn], { type: "application/x-chess-pgn" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "pointchess_react.pgn";
  a.click();
  URL.revokeObjectURL(url);
});

eloSlider.addEventListener("input", async () => {
  eloValueEl.textContent = eloSlider.value;
});
eloSlider.addEventListener("change", async () => {
  await fetch("/api/set_elo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ elo: parseInt(eloSlider.value, 10) }),
  });
});

sideSelect.addEventListener("change", () => {
  // No-op until "New Game" is pressed; rendering still flips.
  if (state) {
    state.human_color = sideSelect.value;
    render();
  }
});

refreshState();
