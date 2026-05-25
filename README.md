# ChessBot Pro

A real-time chess assistant that captures your screen, detects the board, classifies pieces using a CNN, and overlays Stockfish's best moves as a transparent click-through display.

## Features

- **Auto Board Detection** — Automatically finds your chessboard on screen by analyzing pixel transitions
- **CNN Piece Recognition** — A trained convolutional neural network identifies all 64 squares in real time
- **Multi-PV Engine Analysis** — Queries Stockfish for the top 5 candidate moves with centipawn evaluation
- **Move Classification** — Labels moves as Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, or Blunder
- **Transparent Overlay** — Draws color-coded move arrows directly over your board (invisible to screen capture)
- **Opening Book Support** — Polyglot (.bin) and custom text-format (.book) opening books
- **Autoplay Mode** — Optionally plays moves automatically with human-like mouse movement
- **Hotkey Controls** — Alt+W (start as White), Alt+B (start as Black), Alt+X (stop)

## Requirements

The executable contains only the application code and Python libraries. You need to provide the following files alongside `ChessBotPro.exe`:

### Required

| File | Description |
|------|-------------|
| `chess_piece_model.pth` | Trained CNN model weights. Train your own using `train_model.py` or download from [Releases](../../releases). |
| `engine/stockfish.exe` | Stockfish chess engine. Download from [stockfishchess.org](https://stockfishchess.org/download/). |

### Optional

| File | Description |
|------|-------------|
| `Books/*.bin` or `Books/*.book` | Opening book files. Polyglot binary format or custom text format. |

### Expected Folder Layout

```
ChessBotPro/
├── ChessBotPro.exe
├── chess_piece_model.pth
├── app_logo.ico
├── engine/
│   └── stockfish.exe
└── Books/                  (optional)
    ├── Human.bin
    ├── GM.book
    └── ...
```

## How to Use

1. **Launch** `ChessBotPro.exe`
2. **Set Engine Path** — Browse to your `stockfish.exe` or place it at `engine/stockfish.exe`
3. **Detect Board** — Click "Auto-Detect Chess Board" with a chessboard visible on screen, or manually enter board coordinates in Settings
4. **Start Analysis** — Click "Start (White)" or "Start (Black)", or use hotkeys:
   - `Alt+W` — Start as White
   - `Alt+B` — Start as Black
   - `Alt+X` — Stop
5. **View Moves** — The overlay appears on top of your board showing recommended moves with color-coded classifications

### Settings

- **Depth** — Engine search depth (higher = stronger but slower)
- **ELO Limit** — Cap engine strength for practice
- **Threads / Hash** — Stockfish resource allocation
- **Move Display Limits** — Control how many moves of each classification to show
- **Opening Book** — Select a book file for opening theory moves

## Building from Source

### Prerequisites

- Python 3.10+
- CUDA-capable GPU (optional, for faster CNN inference)

### Setup

```bash
git clone https://github.com/yourusername/python_chessbot.git
cd python_chessbot

# Install dependencies (CPU-only PyTorch for smaller install)
pip install -r requirements.txt

# Or with GPU support:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

### Running from Source

```bash
python chessbot_full.py
```

### Building the Executable

```bash
pyinstaller ChessBotPro.spec
```

The output exe will be in `dist/ChessBotPro.exe`.

## Training the Model

If you want to train your own piece recognition model:

1. **Collect training data** — Run `collect_data.py` with a chess board visible on screen at the starting position. This captures and labels 64 square images per frame, plus synthetic background-swapped variants.

2. **Train the CNN** — Run `train_model.py` to train the classifier on the collected dataset. Outputs `chess_piece_model.pth`.

```bash
python collect_data.py
python train_model.py
```

The model classifies squares into 13 classes: `empty`, `wp`, `bp`, `wb`, `bb`, `wn`, `bn`, `wr`, `br`, `wq`, `bq`, `wk`, `bk`.

## Technical Architecture

1. **Screen Capture** (`mss`) — High-performance screenshot of the board region
2. **Board Detection** (`OpenCV` / `NumPy`) — Finds board boundaries via color transition analysis
3. **Piece Recognition** (`PyTorch` CNN) — Batch classifies 64 squares with temporal majority voting
4. **Engine Analysis** (`python-chess` / Stockfish UCI) — Multi-PV search with move classification
5. **Overlay Display** (`Tkinter`) — Transparent, click-through, capture-excluded window

## License

This project is for educational and personal use.
