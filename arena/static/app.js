(() => {
  const FILES = ["a","b","c","d","e","f","g","h"];
  const PIECE_VALUE = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
  const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

  const $ = (id) => document.getElementById(id);
  const boardEl     = $("board");
  const arrowsEl    = $("arrows");
  const SVG_NS      = "http://www.w3.org/2000/svg";
  const statusEl    = $("status");
  const statusText  = $("status-text");
  const startBtn    = $("start-btn");
  const stopBtn     = $("stop-btn");
  const swapBtn     = $("swap-btn");
  const movetimeEl  = $("movetime");
  const maxpliesEl  = $("maxplies");
  const whiteSel    = $("white-select");
  const blackSel    = $("black-select");
  const whiteMeta   = $("white-meta");
  const blackMeta   = $("black-meta");
  const whiteName   = $("white-name");
  const blackName   = $("black-name");
  const whiteTag    = $("white-tag");
  const blackTag    = $("black-tag");
  const whiteCaps   = $("white-captures");
  const blackCaps   = $("black-captures");
  const whiteClock  = $("white-clock");
  const blackClock  = $("black-clock");
  const whiteStats  = $("white-stats");
  const blackStats  = $("black-stats");
  const mWhiteName  = $("m-white-name");
  const mBlackName  = $("m-black-name");
  const playerTop   = $("player-top");
  const playerBot   = $("player-bottom");
  const movelog     = $("movelog");
  const banner      = $("result-banner");
  const bannerRes   = $("banner-result");
  const bannerReason= $("banner-reason");
  const bannerRematch = $("banner-rematch");
  const evalFill    = $("eval-fill");
  const evalText    = $("eval-text");
  const costTbody   = document.querySelector("#cost-table tbody");

  let engines = [];
  let currentEvt = null;
  let currentMatchId = null;

  // ---- board ----
  function buildBoard() {
    boardEl.innerHTML = "";
    for (let r = 7; r >= 0; r--) {
      for (let f = 0; f < 8; f++) {
        const sq = document.createElement("div");
        const isLight = (r + f) % 2 === 1;
        sq.className = "sq " + (isLight ? "light" : "dark");
        sq.dataset.sq = FILES[f] + (r + 1);
        if (r === 0) {
          const c = document.createElement("span");
          c.className = "coord file";
          c.textContent = FILES[f];
          sq.appendChild(c);
        }
        if (f === 0) {
          const c = document.createElement("span");
          c.className = "coord rank";
          c.textContent = (r + 1);
          sq.appendChild(c);
        }
        boardEl.appendChild(sq);
      }
    }
  }

  function renderFEN(fen, fromSq, toSq) {
    const placement = fen.split(" ")[0];
    const ranks = placement.split("/");
    const grid = boardEl.children;
    let i = 0;
    for (let r = 0; r < 8; r++) {
      const row = ranks[r];
      for (const ch of row) {
        if (/[1-8]/.test(ch)) {
          for (let k = 0; k < parseInt(ch, 10); k++) {
            stripPiece(grid[i++]);
          }
        } else {
          setPiece(grid[i++], ch);
        }
      }
    }
    for (const sq of grid) sq.classList.remove("from", "to");
    if (fromSq) {
      const a = boardEl.querySelector(`[data-sq="${fromSq}"]`);
      if (a) a.classList.add("from");
    }
    if (toSq) {
      const b = boardEl.querySelector(`[data-sq="${toSq}"]`);
      if (b) b.classList.add("to");
    }
    drawArrow(fromSq, toSq);
  }

  // ---- move arrow (chess.com-style) ----
  // viewBox is 0..80, each square = 10 units, file a..h on x, rank 8..1 on y.
  function sqCenter(sq) {
    const file = sq.charCodeAt(0) - 97;       // 0..7
    const rank = parseInt(sq[1], 10) - 1;     // 0..7
    return { x: file * 10 + 5, y: (7 - rank) * 10 + 5 };
  }
  function isKnightMove(from, to) {
    const dx = Math.abs(from.x - to.x), dy = Math.abs(from.y - to.y);
    return (dx === 10 && dy === 20) || (dx === 20 && dy === 10);
  }
  function shortenedEndpoint(from, to, shortenBy = 3.2) {
    const dx = to.x - from.x, dy = to.y - from.y;
    const len = Math.hypot(dx, dy);
    if (len === 0) return to;
    const k = (len - shortenBy) / len;
    return { x: from.x + dx * k, y: from.y + dy * k };
  }
  function drawArrow(fromSq, toSq) {
    // Clear previous arrow but keep <defs>.
    arrowsEl.querySelectorAll(".move-arrow").forEach((n) => n.remove());
    if (!fromSq || !toSq || fromSq === toSq) return;
    const from = sqCenter(fromSq);
    const to   = sqCenter(toSq);
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("class", "move-arrow");
    let d;
    if (isKnightMove(from, to)) {
      // L-shape: long leg first, then the short leg into the destination.
      const dx = to.x - from.x, dy = to.y - from.y;
      const corner = Math.abs(dx) > Math.abs(dy)
        ? { x: to.x, y: from.y }
        : { x: from.x, y: to.y };
      const end = shortenedEndpoint(corner, to);
      d = `M ${from.x} ${from.y} L ${corner.x} ${corner.y} L ${end.x} ${end.y}`;
    } else {
      const end = shortenedEndpoint(from, to);
      d = `M ${from.x} ${from.y} L ${end.x} ${end.y}`;
    }
    path.setAttribute("d", d);
    arrowsEl.appendChild(path);
  }

  function stripPiece(sq) {
    const p = sq.querySelector(".piece");
    if (p) p.remove();
  }
  function setPiece(sq, ch) {
    let p = sq.querySelector(".piece");
    if (!p) {
      p = document.createElement("div");
      p.className = "piece";
      sq.appendChild(p);
    }
    const url = window.PIECE_SVG[ch];
    if (url) p.style.backgroundImage = `url("${url}")`;
  }

  // ---- engines ----
  async function loadEngines() {
    const r = await fetch("/api/engines");
    const data = await r.json();
    engines = data.engines;
    for (const sel of [whiteSel, blackSel]) {
      sel.innerHTML = "";
      engines.forEach((e) => {
        const opt = document.createElement("option");
        opt.value = e.id;
        opt.textContent = e.label;
        sel.appendChild(opt);
      });
    }
    if (engines.length >= 2) {
      whiteSel.value = engines[0].id;
      blackSel.value = engines[1].id;
    }
    renderMeta();
    renderCostTable();
  }

  function fmtCost(e) {
    if (e.build_cost_usd != null) return `$${Number(e.build_cost_usd).toFixed(2)}`;
    return "—";
  }
  function fmtTokens(e) {
    if (e.build_tokens == null) return "—";
    if (e.build_tokens >= 1_000_000) return (e.build_tokens / 1_000_000).toFixed(2) + "M";
    if (e.build_tokens >= 1_000)    return (e.build_tokens / 1_000).toFixed(1) + "k";
    return String(e.build_tokens);
  }
  function metaCard(e) {
    return `
      <div class="blurb">${e.blurb}</div>
      <div class="meta-row">
        <span class="chip">${e.build_pattern || "—"}</span>
        <span class="chip">${e.loc ?? "—"} LOC</span>
      </div>
    `;
  }
  function renderMeta() {
    const w = engines.find((e) => e.id === whiteSel.value);
    const b = engines.find((e) => e.id === blackSel.value);
    if (w) whiteMeta.innerHTML = metaCard(w);
    if (b) blackMeta.innerHTML = metaCard(b);
    whiteName.textContent = w ? w.label : "—";
    blackName.textContent = b ? b.label : "—";
    whiteTag.textContent  = w ? (w.build_pattern || "engine") : "—";
    blackTag.textContent  = b ? (b.build_pattern || "engine") : "—";
    mWhiteName.textContent = w ? w.label : "white";
    mBlackName.textContent = b ? b.label : "black";
    resetStats();
  }

  function renderCostTable() {
    costTbody.innerHTML = "";
    engines.forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td title="${e.label}">${e.label}</td>
        <td>${fmtCost(e)}</td>
        <td>${fmtTokens(e)}</td>
        <td>${e.loc ?? "—"}</td>
      `;
      costTbody.appendChild(tr);
    });
  }

  // ---- live metrics ----
  function statBlock(s) {
    if (!s) {
      return `
        <div class="m-stat"><div class="k">depth</div><div class="v">—</div></div>
        <div class="m-stat"><div class="k">eval</div><div class="v">—</div></div>
        <div class="m-stat"><div class="k">nps</div><div class="v">—</div></div>
        <div class="m-stat"><div class="k">moves</div><div class="v">—</div></div>
        <div class="m-stat"><div class="k">nodes</div><div class="v">—</div></div>
        <div class="m-stat"><div class="k">avg ms</div><div class="v">—</div></div>
      `;
    }
    const score = s.last_score_cp == null ? "—" :
      ((s.last_score_cp >= 0 ? "+" : "") + (s.last_score_cp / 100).toFixed(2));
    const nodes = s.nodes_total >= 1000
      ? (s.nodes_total / 1000).toFixed(1) + "k"
      : (s.nodes_total ?? 0).toString();
    return `
      <div class="m-stat"><div class="k">depth</div><div class="v">${s.last_depth ?? "—"}</div></div>
      <div class="m-stat"><div class="k">eval</div><div class="v">${score}</div></div>
      <div class="m-stat"><div class="k">nps</div><div class="v">${s.last_nps != null ? (s.last_nps/1000).toFixed(1)+"k" : "—"}</div></div>
      <div class="m-stat"><div class="k">moves</div><div class="v">${s.moves}</div></div>
      <div class="m-stat"><div class="k">nodes</div><div class="v">${nodes}</div></div>
      <div class="m-stat"><div class="k">avg ms</div><div class="v">${s.avg_time_ms ?? "—"}</div></div>
    `;
  }
  function resetStats() {
    whiteStats.innerHTML = statBlock(null);
    blackStats.innerHTML = statBlock(null);
    whiteClock.textContent = "0.0s";
    blackClock.textContent = "0.0s";
    whiteCaps.innerHTML = "";
    blackCaps.innerHTML = "";
    setEval(0, null);
    setThinking(null);
  }

  function applyStats(s, whiteId, blackId) {
    if (!s) return;
    whiteStats.innerHTML = statBlock(s[whiteId]);
    blackStats.innerHTML = statBlock(s[blackId]);
    if (s[whiteId]) whiteClock.textContent = fmtClock(s[whiteId].time_ms_total);
    if (s[blackId]) blackClock.textContent = fmtClock(s[blackId].time_ms_total);
  }

  function fmtClock(ms) {
    const s = (ms || 0) / 1000;
    if (s < 60) return s.toFixed(1) + "s";
    const m = Math.floor(s / 60);
    const r = (s - m * 60).toFixed(1);
    return `${m}:${r.padStart(4, "0")}`;
  }

  // ---- eval bar ----
  function setEval(scoreCp, mate) {
    let label;
    let pct;
    if (mate != null) {
      label = "M" + Math.abs(mate);
      pct = mate > 0 ? 100 : 0;
    } else {
      const cp = scoreCp || 0;
      label = (cp >= 0 ? "+" : "") + (cp / 100).toFixed(2);
      // sigmoid-ish so small advantages move the bar visibly
      pct = 50 + 50 * (2 / (1 + Math.exp(-cp / 350)) - 1);
      pct = Math.max(2, Math.min(98, pct));
    }
    evalFill.style.height = pct + "%";
    evalText.textContent = label;
  }

  // ---- captures ----
  function recomputeCaptures(fen) {
    // Standard starting counts; subtract what's on board to find captured.
    const standard = { P: 8, N: 2, B: 2, R: 2, Q: 1, p: 8, n: 2, b: 2, r: 2, q: 1 };
    const counts = {};
    for (const ch of fen.split(" ")[0]) {
      if (/[a-zA-Z]/.test(ch)) counts[ch] = (counts[ch] || 0) + 1;
    }
    // captured-by-white = missing black pieces; captured-by-black = missing white.
    const capturedByWhite = []; let blackLost = 0;
    const capturedByBlack = []; let whiteLost = 0;
    for (const [k, v] of Object.entries(standard)) {
      const have = counts[k] || 0;
      const missing = Math.max(0, v - have);
      const wasBlack = (k === k.toLowerCase());
      for (let i = 0; i < missing; i++) {
        if (wasBlack) { capturedByWhite.push(k); blackLost += PIECE_VALUE[k]; }
        else          { capturedByBlack.push(k.toLowerCase()); whiteLost += PIECE_VALUE[k.toLowerCase()]; }
      }
    }
    const sortOrder = "qrbnp";
    capturedByWhite.sort((a, b) => sortOrder.indexOf(a) - sortOrder.indexOf(b));
    capturedByBlack.sort((a, b) => sortOrder.indexOf(a) - sortOrder.indexOf(b));
    const diff = blackLost - whiteLost; // positive = white ahead
    renderCaps(whiteCaps, capturedByWhite, diff > 0 ? "+" + diff : "");
    renderCaps(blackCaps, capturedByBlack, diff < 0 ? "+" + Math.abs(diff) : "");
  }
  function renderCaps(el, pieces, diffLabel) {
    const glyph = { p: "♟", n: "♞", b: "♝", r: "♜", q: "♛" };
    const html = pieces.map((p) => glyph[p]).join("") +
      (diffLabel ? `<span class="material-diff">${diffLabel}</span>` : "");
    el.innerHTML = html;
  }

  // ---- move log ----
  function appendMove(ev) {
    if (movelog.querySelector(".movelog-empty")) movelog.innerHTML = "";
    const ply = ev.ply;
    const moveNum = Math.ceil(ply / 2);
    const isWhite = ev.color === "white";
    document.querySelectorAll(".movelog .move.latest").forEach((n) => n.classList.remove("latest"));
    if (isWhite) {
      const num = document.createElement("div");
      num.className = "ply-num";
      num.textContent = moveNum;
      movelog.appendChild(num);
    }
    const cell = document.createElement("div");
    cell.className = "move latest";
    const score = ev.mate != null ? "#" + ev.mate :
                  ev.score_cp != null ? ((ev.score_cp >= 0 ? "+" : "") + (ev.score_cp / 100).toFixed(2)) : "";
    cell.innerHTML = `<span class="san">${ev.san}</span><span class="meta">d${ev.depth ?? "?"} · ${score}</span>`;
    movelog.appendChild(cell);
    movelog.scrollTop = movelog.scrollHeight;
  }

  // ---- thinking indicator ----
  function setThinking(color) {
    playerTop.classList.toggle("thinking", color === "black");
    playerBot.classList.toggle("thinking", color === "white");
  }
  function setStatus(text, cls) {
    statusText.textContent = text;
    statusEl.className = "status-pill " + (cls || "");
  }

  // ---- match ----
  async function startMatch() {
    if (currentEvt) currentEvt.close();
    movelog.innerHTML = '<div class="movelog-empty">No moves yet</div>';
    banner.setAttribute("hidden", "");
    banner.hidden = true;
    resetStats();
    renderFEN(START_FEN);
    recomputeCaptures(START_FEN);
    const body = {
      white: whiteSel.value,
      black: blackSel.value,
      movetime_ms: parseInt(movetimeEl.value, 10),
      max_plies: parseInt(maxpliesEl.value, 10),
    };
    setStatus("starting…", "live");
    startBtn.disabled = true;
    stopBtn.disabled = false;
    let r;
    try {
      r = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (e) {
      setStatus("network error", "error");
      startBtn.disabled = false;
      stopBtn.disabled = true;
      return;
    }
    if (!r.ok) {
      setStatus("error " + r.status, "error");
      startBtn.disabled = false;
      stopBtn.disabled = true;
      return;
    }
    const { match_id } = await r.json();
    currentMatchId = match_id;
    openStream(match_id, body.white, body.black);
  }

  function openStream(mid, whiteId, blackId) {
    const evt = new EventSource(`/api/match/${mid}/stream`);
    currentEvt = evt;
    setStatus("playing", "live");
    setThinking("white");
    evt.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "init") {
        renderFEN(ev.fen);
        recomputeCaptures(ev.fen);
      } else if (ev.type === "move") {
        const fromSq = ev.uci.slice(0, 2);
        const toSq = ev.uci.slice(2, 4);
        renderFEN(ev.fen, fromSq, toSq);
        recomputeCaptures(ev.fen);
        appendMove(ev);
        applyStats(ev.stats, whiteId, blackId);
        // Eval bar: keep the most-recent eval, but always from white's POV.
        let cp = ev.score_cp;
        let mate = ev.mate;
        if (cp != null && ev.color === "black") cp = -cp;
        if (mate != null && ev.color === "black") mate = -mate;
        setEval(cp, mate);
        setThinking(ev.color === "white" ? "black" : "white");
      } else if (ev.type === "end") {
        applyStats(ev.stats, whiteId, blackId);
        setThinking(null);
        startBtn.disabled = false;
        stopBtn.disabled = true;
        showResult(ev);
        evt.close();
        currentEvt = null;
      }
    };
    evt.onerror = () => {
      setStatus("disconnected", "error");
      startBtn.disabled = false;
      stopBtn.disabled = true;
      evt.close();
      currentEvt = null;
    };
  }

  function showResult(ev) {
    const map = { "1-0": "1 – 0", "0-1": "0 – 1", "1/2-1/2": "½ – ½" };
    bannerRes.textContent = map[ev.result] || ev.result || "—";
    bannerReason.textContent = ev.reason || "";
    banner.hidden = false;
    setStatus(ev.result || "done", ev.result === "*" ? "error" : "done");
  }

  async function stopMatch() {
    if (!currentMatchId) return;
    await fetch(`/api/match/${currentMatchId}/stop`, { method: "POST" });
  }

  function swapColors() {
    const w = whiteSel.value;
    whiteSel.value = blackSel.value;
    blackSel.value = w;
    renderMeta();
  }

  // ---- wire ----
  buildBoard();
  renderFEN(START_FEN);
  loadEngines().then(() => { resetStats(); recomputeCaptures(START_FEN); });
  whiteSel.addEventListener("change", renderMeta);
  blackSel.addEventListener("change", renderMeta);
  startBtn.addEventListener("click", startMatch);
  stopBtn.addEventListener("click", stopMatch);
  swapBtn.addEventListener("click", swapColors);
  bannerRematch.addEventListener("click", () => {
    banner.setAttribute("hidden", "");
    banner.hidden = true;
    startMatch();
  });
})();
