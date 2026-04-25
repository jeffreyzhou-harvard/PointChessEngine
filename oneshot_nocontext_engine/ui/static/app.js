// PointChess Engine - Browser UI

const PIECE_UNICODE = {
    'K': '\u2654', 'Q': '\u2655', 'R': '\u2656', 'B': '\u2657', 'N': '\u2658', 'P': '\u2659',
    'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
};

let gameState = null;
let selectedSquare = null;
let playerColor = 'white';
let pendingPromotion = null;
let isThinking = false;
let lastMoveFrom = null;
let lastMoveTo = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchState();
});

async function fetchState() {
    try {
        const res = await fetch('/api/state');
        gameState = await res.json();
        renderBoard();
        renderMoveList();
        updateStatus();
    } catch (e) {
        console.error('Failed to fetch state:', e);
    }
}

function setColor(color) {
    playerColor = color;
    document.getElementById('btn-white').classList.toggle('active', color === 'white');
    document.getElementById('btn-black').classList.toggle('active', color === 'black');
}

async function newGame() {
    const elo = parseInt(document.getElementById('elo-slider').value);
    setThinking(true);
    try {
        const res = await fetch('/api/new', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({color: playerColor, elo: elo}),
        });
        gameState = await res.json();
        selectedSquare = null;
        lastMoveFrom = null;
        lastMoveTo = null;
        renderBoard();
        renderMoveList();
        updateStatus();
    } catch (e) {
        console.error('Failed to start new game:', e);
    }
    setThinking(false);
}

function renderBoard() {
    const boardEl = document.getElementById('board');
    boardEl.innerHTML = '';

    if (!gameState) return;

    const flipped = gameState.playerColor === 'black';

    // Update rank labels
    const rankLabels = document.getElementById('rank-labels');
    const ranks = flipped ? ['1','2','3','4','5','6','7','8'] : ['8','7','6','5','4','3','2','1'];
    rankLabels.innerHTML = ranks.map(r => `<span>${r}</span>`).join('');

    // Update file labels
    const fileLabels = document.querySelector('.board-labels-top');
    const files = flipped ? ['h','g','f','e','d','c','b','a'] : ['a','b','c','d','e','f','g','h'];
    fileLabels.innerHTML = files.map(f => `<span>${f}</span>`).join('');

    // Find legal target squares for selected piece
    const legalTargets = new Set();
    const legalCaptures = new Set();
    if (selectedSquare && gameState.legalMoves) {
        for (const m of gameState.legalMoves) {
            if (m.from === selectedSquare) {
                legalTargets.add(m.to);
                // Check if it's a capture
                const toRow = 8 - parseInt(m.to[1]);
                const toCol = m.to.charCodeAt(0) - 97;
                if (gameState.board[toRow][toCol] !== null) {
                    legalCaptures.add(m.to);
                }
            }
        }
    }

    // Find king in check
    let checkSquare = null;
    if (gameState.inCheck) {
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const p = gameState.board[r][c];
                if (p && p.toLowerCase() === 'k') {
                    const isWhiteKing = p === 'K';
                    if ((gameState.turn === 'white' && isWhiteKing) ||
                        (gameState.turn === 'black' && !isWhiteKing)) {
                        checkSquare = String.fromCharCode(97 + c) + (8 - r);
                    }
                }
            }
        }
    }

    for (let displayRow = 0; displayRow < 8; displayRow++) {
        for (let displayCol = 0; displayCol < 8; displayCol++) {
            const r = flipped ? 7 - displayRow : displayRow;
            const c = flipped ? 7 - displayCol : displayCol;

            const sq = document.createElement('div');
            const algebraic = String.fromCharCode(97 + c) + (8 - r);
            const isLight = (r + c) % 2 === 0;

            sq.className = 'square ' + (isLight ? 'light' : 'dark');
            sq.dataset.square = algebraic;

            // Highlight selected square
            if (selectedSquare === algebraic) {
                sq.classList.add('selected');
            }

            // Highlight last move
            if (lastMoveFrom === algebraic || lastMoveTo === algebraic) {
                sq.classList.add('last-move');
            }

            // Show legal move dots
            if (legalTargets.has(algebraic)) {
                if (legalCaptures.has(algebraic)) {
                    sq.classList.add('legal-target-capture');
                } else {
                    sq.classList.add('legal-target');
                }
            }

            // Check highlight
            if (checkSquare === algebraic) {
                sq.classList.add('check');
            }

            // Piece
            const piece = gameState.board[r][c];
            if (piece) {
                const pieceEl = document.createElement('span');
                pieceEl.className = 'piece ' + (piece === piece.toUpperCase() ? 'white' : 'black');
                pieceEl.textContent = PIECE_UNICODE[piece];
                sq.appendChild(pieceEl);
            }

            sq.addEventListener('click', () => onSquareClick(algebraic));
            boardEl.appendChild(sq);
        }
    }
}

function onSquareClick(algebraic) {
    if (!gameState || gameState.gameOver || isThinking) return;

    // Not player's turn
    if (gameState.turn !== gameState.playerColor) return;

    if (selectedSquare) {
        // Try to make a move
        if (selectedSquare === algebraic) {
            // Deselect
            selectedSquare = null;
            renderBoard();
            return;
        }

        // Check if this is a legal move
        const matchingMoves = gameState.legalMoves.filter(
            m => m.from === selectedSquare && m.to === algebraic
        );

        if (matchingMoves.length > 0) {
            // Check if promotion is needed
            const promoMoves = matchingMoves.filter(m => m.promotion);
            if (promoMoves.length > 0) {
                showPromotionDialog(selectedSquare, algebraic);
                return;
            }
            makeMove(matchingMoves[0].uci);
        } else {
            // Check if clicking own piece to reselect
            const row = 8 - parseInt(algebraic[1]);
            const col = algebraic.charCodeAt(0) - 97;
            const piece = gameState.board[row][col];
            if (piece) {
                const isOwnPiece = (gameState.playerColor === 'white' && piece === piece.toUpperCase()) ||
                                   (gameState.playerColor === 'black' && piece === piece.toLowerCase());
                if (isOwnPiece) {
                    selectedSquare = algebraic;
                    renderBoard();
                    return;
                }
            }
            selectedSquare = null;
            renderBoard();
        }
    } else {
        // Select a piece
        const row = 8 - parseInt(algebraic[1]);
        const col = algebraic.charCodeAt(0) - 97;
        const piece = gameState.board[row][col];

        if (piece) {
            const isOwnPiece = (gameState.playerColor === 'white' && piece === piece.toUpperCase()) ||
                               (gameState.playerColor === 'black' && piece === piece.toLowerCase());
            if (isOwnPiece) {
                selectedSquare = algebraic;
                renderBoard();
            }
        }
    }
}

function showPromotionDialog(from, to) {
    pendingPromotion = {from, to};
    const modal = document.getElementById('promotion-modal');
    const choices = document.getElementById('promotion-choices');
    const isWhite = gameState.playerColor === 'white';

    const pieces = isWhite ? ['Q', 'R', 'B', 'N'] : ['q', 'r', 'b', 'n'];
    const promoChars = ['q', 'r', 'b', 'n'];

    choices.innerHTML = '';
    pieces.forEach((p, i) => {
        const sq = document.createElement('div');
        sq.className = 'square dark';
        const pieceEl = document.createElement('span');
        pieceEl.className = 'piece ' + (isWhite ? 'white' : 'black');
        pieceEl.textContent = PIECE_UNICODE[p];
        sq.appendChild(pieceEl);
        sq.addEventListener('click', () => {
            modal.style.display = 'none';
            makeMove(from + to + promoChars[i]);
            pendingPromotion = null;
        });
        choices.appendChild(sq);
    });

    modal.style.display = 'flex';
}

async function makeMove(uci) {
    selectedSquare = null;
    setThinking(true);

    // Track last move visually
    lastMoveFrom = uci.substring(0, 2);
    lastMoveTo = uci.substring(2, 4);

    try {
        const res = await fetch('/api/move', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({move: uci}),
        });

        if (res.ok) {
            gameState = await res.json();
            // Update last move to engine's response
            if (gameState.moveList.length >= 2) {
                // The engine also moved, but we don't have its UCI easily
                // Just keep the highlighting from the board state
            }
            renderBoard();
            renderMoveList();
            updateStatus();
        } else {
            const err = await res.json();
            console.error('Move error:', err);
        }
    } catch (e) {
        console.error('Failed to make move:', e);
    }

    setThinking(false);
}

async function undoMove() {
    if (isThinking) return;
    try {
        const res = await fetch('/api/undo', {method: 'POST'});
        gameState = await res.json();
        selectedSquare = null;
        lastMoveFrom = null;
        lastMoveTo = null;
        renderBoard();
        renderMoveList();
        updateStatus();
    } catch (e) {
        console.error('Failed to undo:', e);
    }
}

async function resign() {
    if (!gameState || gameState.gameOver || isThinking) return;
    if (!confirm('Are you sure you want to resign?')) return;

    try {
        const res = await fetch('/api/resign', {method: 'POST'});
        gameState = await res.json();
        renderBoard();
        updateStatus();
    } catch (e) {
        console.error('Failed to resign:', e);
    }
}

async function exportPGN() {
    try {
        const res = await fetch('/api/pgn');
        const data = await res.json();
        // Copy to clipboard
        await navigator.clipboard.writeText(data.pgn);
        alert('PGN copied to clipboard!');
    } catch (e) {
        console.error('Failed to export PGN:', e);
    }
}

function renderMoveList() {
    const el = document.getElementById('move-list');
    if (!gameState || !gameState.moveList.length) {
        el.innerHTML = '<div style="color:#666;font-style:italic;">No moves yet</div>';
        return;
    }

    let html = '';
    for (let i = 0; i < gameState.moveList.length; i += 2) {
        const moveNum = Math.floor(i / 2) + 1;
        const white = gameState.moveList[i];
        const black = i + 1 < gameState.moveList.length ? gameState.moveList[i + 1] : '';
        html += `<div class="move-pair">
            <span class="move-number">${moveNum}.</span>
            <span class="move">${white}</span>
            <span class="move">${black}</span>
        </div>`;
    }
    el.innerHTML = html;
    el.scrollTop = el.scrollHeight;
}

function updateStatus() {
    const el = document.getElementById('status');
    const fenEl = document.getElementById('fen-display');

    if (!gameState) {
        el.textContent = 'Loading...';
        return;
    }

    fenEl.textContent = gameState.fen;

    if (gameState.gameOver) {
        el.textContent = gameState.gameResult;
        el.className = 'status-bar';
        return;
    }

    if (isThinking) {
        el.textContent = 'Engine is thinking...';
        el.className = 'status-bar thinking';
        return;
    }

    const turn = gameState.turn === 'white' ? 'White' : 'Black';
    const isPlayerTurn = gameState.turn === gameState.playerColor;

    if (gameState.inCheck) {
        el.textContent = `${turn} is in check! ${isPlayerTurn ? 'Your move.' : 'Engine thinking...'}`;
    } else {
        el.textContent = isPlayerTurn ? `Your turn (${turn})` : `Engine's turn (${turn})`;
    }
    el.className = 'status-bar';
}

function setThinking(thinking) {
    isThinking = thinking;
    updateStatus();
}
