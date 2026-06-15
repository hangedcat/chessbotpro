import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import keyboard
import chess
import chess.engine
import threading
import time
import os
import sys
import cv2
import numpy as np
import mss
import ctypes
import random

# Classes structure
CLASSES = ['empty', 'wp', 'wn', 'wb', 'wr', 'wq', 'wk', 'bp', 'bn', 'bb', 'br', 'bq', 'bk']

class BboxPreviewOverlay:
    """Transparent always-on-top window that draws the board bounding box for visual alignment."""
    def __init__(self, parent, x, y, size, sq_size):
        self.win = tk.Toplevel(parent)
        self.win.title("BboxPreview")
        self.win.overrideredirect(True)
        self.win.attributes("-transparentcolor", "black")
        self.win.attributes("-topmost", True)
        self.win.config(bg="black")
        self._place(x, y, size)

        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Make click-through
        self.win.after(100, self._apply_click_through)
        self._draw(size, sq_size)

    def _apply_click_through(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "BboxPreview")
            if not hwnd:
                hwnd = self.win.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED     = 0x00080000
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        except Exception:
            pass

    def _place(self, x, y, size):
        # Add a small margin so the border itself is visible even at the screen edge
        margin = 4
        self.win.geometry(f"{size + margin*2}x{size + margin*2}+{x - margin}+{y - margin}")
        self._margin = margin

    def _draw(self, size, sq_size):
        self.canvas.delete("all")
        m = self._margin
        # Outer border in bright blue
        self.canvas.create_rectangle(m, m, m + size, m + size,
                                     outline="#3399ff", width=3)
        # Grid lines for each square in semi-transparent blue
        for i in range(1, 8):
            self.canvas.create_line(m + i * sq_size, m,
                                    m + i * sq_size, m + size,
                                    fill="#3399ff", width=1, dash=(4, 4))
            self.canvas.create_line(m,              m + i * sq_size,
                                    m + size,       m + i * sq_size,
                                    fill="#3399ff", width=1, dash=(4, 4))
        # Corner tick marks in yellow for easier alignment
        tick = 12
        for cx, cy in [(m, m), (m + size, m), (m, m + size), (m + size, m + size)]:
            dx = tick if cx == m else -tick
            dy = tick if cy == m else -tick
            self.canvas.create_line(cx, cy, cx + dx, cy, fill="#ffff00", width=3)
            self.canvas.create_line(cx, cy, cx, cy + dy, fill="#ffff00", width=3)

    def update(self, x, y, size, sq_size):
        self._place(x, y, size)
        self.canvas.config(width=size + self._margin * 2,
                           height=size + self._margin * 2)
        self._draw(size, sq_size)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class MoveOverlay:
    def __init__(self, parent, x, y, size, sq_size):
        self.parent = parent
        self.x = x
        self.y = y
        self.size = size
        self.sq_size = sq_size
        
        self.win = tk.Toplevel(parent)
        self.win.title("Move Overlay")
        self.win.overrideredirect(True)
        self.win.geometry(f"{size}x{size}+{x}+{y}")
        
        # Transparent, always-on-top window attributes
        self.win.attributes("-transparentcolor", "green")
        self.win.attributes("-topmost", True)
        self.win.config(bg="green")
        
        self.canvas = tk.Canvas(self.win, width=size, height=size, bg="green", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Exclude the overlay window from screenshots to prevent CNN classification errors
        self.win.after(100, self.apply_capture_exclusion)
        
    def apply_capture_exclusion(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Try finding the top-level window handle by title
            hwnd = user32.FindWindowW(None, "Move Overlay")
            if not hwnd:
                # Climb parent hierarchy if not found by title
                hwnd = self.win.winfo_id()
                while True:
                    parent = user32.GetParent(hwnd)
                    if not parent:
                        break
                    hwnd = parent
            if hwnd:
                # WDA_EXCLUDEFROMCAPTURE = 0x00000011
                ret = user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                if not ret:
                    user32.SetWindowDisplayAffinity(hwnd, 0x00000001)
                    
                # Make window mouse-transparent (click-through) silently
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_LAYERED = 0x00080000
                current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
        except Exception:
            pass
            
    def draw_moves(self, moves_data, flipped):
        self.canvas.delete("all")
        if not moves_data:
            return
            
        # Draw from lowest rank (index 4 down to 0) so the best move (index 0) is drawn on top
        for rank in range(len(moves_data) - 1, -1, -1):
            item = moves_data[rank]
            move_uci = item["move"]
            if not move_uci or len(move_uci) < 4:
                continue
                
            s_file = ord(move_uci[0]) - ord('a')
            s_rank = int(move_uci[1]) - 1
            e_file = ord(move_uci[2]) - ord('a')
            e_rank = int(move_uci[3]) - 1
            
            if not flipped:
                s_col = s_file
                s_row = 7 - s_rank
                e_col = e_file
                e_row = 7 - e_rank
            else:
                s_col = 7 - s_file
                s_row = s_rank
                e_col = 7 - e_file
                e_row = e_rank
                
            move_color = item["color"]
            move_type = item["type"]
            
            # Offset coordinates based on rank to display concentric squares for overlapping moves
            offset_box = rank * 2
            
            x1_start = s_col * self.sq_size + 4 + offset_box
            y1_start = s_row * self.sq_size + 4 + offset_box
            x2_start = (s_col + 1) * self.sq_size - 4 - offset_box
            y2_start = (s_row + 1) * self.sq_size - 4 - offset_box
            
            x1_end = e_col * self.sq_size + 4 + offset_box
            y1_end = e_row * self.sq_size + 4 + offset_box
            x2_end = (e_col + 1) * self.sq_size - 4 - offset_box
            y2_end = (e_row + 1) * self.sq_size - 4 - offset_box
            
            # Draw starting square box (thick border)
            self.canvas.create_rectangle(x1_start, y1_start, x2_start, y2_start, outline=move_color, width=4)
            
            # Draw target square box (thick border)
            self.canvas.create_rectangle(x1_end, y1_end, x2_end, y2_end, outline=move_color, width=4)
            
            # Draw a thin dashed line between centers to show connection
            cx1 = int((s_col + 0.5) * self.sq_size)
            cy1 = int((s_row + 0.5) * self.sq_size)
            cx2 = int((e_col + 0.5) * self.sq_size)
            cy2 = int((e_row + 0.5) * self.sq_size)
            self.canvas.create_line(cx1, cy1, cx2, cy2, fill=move_color, width=2, dash=(6, 4))
            
            # Draw labels on the target square upper-left, stacked vertically if multiple
            # moves target the same square: +/- score on top, classification below.
            tx = e_col * self.sq_size + 6
            ty = e_row * self.sq_size + 6 + (rank * 24)

            score_text = item.get("score", "")
            if score_text:
                self.canvas.create_text(tx + 1, ty + 1, text=score_text, fill="black", font=("Arial", 8, "bold"), anchor=tk.NW)
                self.canvas.create_text(tx, ty, text=score_text, fill=move_color, font=("Arial", 8, "bold"), anchor=tk.NW)
                ty += 11

            self.canvas.create_text(tx + 1, ty + 1, text=move_type, fill="black", font=("Arial", 8, "bold"), anchor=tk.NW)
            self.canvas.create_text(tx, ty, text=move_type, fill=move_color, font=("Arial", 8, "bold"), anchor=tk.NW)

    def clear(self):
        self.canvas.delete("all")
        
    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass

class ChessBotPro:
    def __init__(self, root):
        self.root = root
        self.root.title("ChessBot Pro - Full ML Version")
        self.root.geometry("500x500")
        self.root.resizable(False, False)

        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(self.script_dir, "app_logo.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        
        # State
        self.engine_path = "Stockfish.exe"
        self.engine = None
        self.maia_engine = None  # Optional lc0/Maia engine for human-like move choice
        self.is_running = False
        self.board_bbox = None  # (x, y, width, height)
        self.sq_size = 0
        self.bbox_preview = None  # BboxPreviewOverlay instance when active
        self.board_x_var = tk.IntVar(value=0)
        self.board_y_var = tk.IntVar(value=0)
        self.board_size_var = tk.IntVar(value=0)
        self.board_x_var.trace_add("write", self.update_board_from_settings)
        self.board_y_var.trace_add("write", self.update_board_from_settings)
        self.board_size_var.trace_add("write", self.update_board_from_settings)
        
        self.model = None
        self.torch = None
        self.transforms = None
        self.device = None
        self.board_history = []
        self.overlay = None
        self.config_path = os.path.join(self.script_dir, "config.json")
        self.book_path = os.path.join(self.script_dir, "Books", "GM.book")
        self.book_lines = []
        self.flipped_var = tk.BooleanVar(value=False)
        self.autoplay_var = tk.BooleanVar(value=False)
        self.is_moving_mouse = False
        self.last_clicked_fen = ""
        self.depth_var = tk.IntVar(value=15)
        self.limit_elo_var = tk.BooleanVar(value=False)
        self.elo_var = tk.IntVar(value=2000)
        self.skill_var = tk.IntVar(value=20)
        self.threads_var = tk.IntVar(value=1)
        self.hash_var = tk.IntVar(value=16)
        self.use_time_limit_var = tk.BooleanVar(value=False)
        self.time_limit_var = tk.DoubleVar(value=1.0)
        self.max_brilliant_var = tk.IntVar(value=1)
        self.max_great_var = tk.IntVar(value=1)
        self.max_best_var = tk.IntVar(value=3)
        self.max_excellent_var = tk.IntVar(value=3)
        self.max_good_var = tk.IntVar(value=3)
        self.max_inaccuracy_var = tk.IntVar(value=1)
        self.max_mistake_var = tk.IntVar(value=1)
        self.max_blunder_var = tk.IntVar(value=1)

        # Human Engine (Maia / lc0): when enabled, Maia picks the move to recommend/play
        # while Stockfish still provides the evaluation scores and classifications.
        self.maia_enabled_var = tk.BooleanVar(value=False)
        self.maia_path_var = tk.StringVar(value="lc0.exe")
        self.maia_weights_var = tk.StringVar(value="")

        self.create_widgets()

        # Trace settings for auto-saving and UI updates
        self.depth_var.trace_add("write", self.save_config)
        self.limit_elo_var.trace_add("write", self._update_strength_ui)
        self.elo_var.trace_add("write", self._update_strength_ui)
        self.skill_var.trace_add("write", self._update_strength_ui)
        self.threads_var.trace_add("write", self.save_config)
        self.hash_var.trace_add("write", self.save_config)
        self.flipped_var.trace_add("write", self.save_config)
        self.autoplay_var.trace_add("write", self.save_config)
        self.use_time_limit_var.trace_add("write", self._update_analysis_mode_ui)
        self.time_limit_var.trace_add("write", self.save_config)
        for _v in (self.max_brilliant_var, self.max_great_var, self.max_best_var,
                   self.max_excellent_var, self.max_good_var, self.max_inaccuracy_var,
                   self.max_mistake_var, self.max_blunder_var):
            _v.trace_add("write", self.save_config)
        self.maia_enabled_var.trace_add("write", self.save_config)
        self.maia_path_var.trace_add("write", self.save_config)
        self.maia_weights_var.trace_add("write", self.save_config)

        self.load_config()
        self._update_strength_ui()
        self._update_analysis_mode_ui()
        
    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)
        
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Control Panel")
        
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings")

        # Wrap settings content in a scrollable canvas so nothing gets clipped
        _settings_canvas = tk.Canvas(settings_frame, highlightthickness=0)
        _settings_scroll = ttk.Scrollbar(settings_frame, orient=tk.VERTICAL, command=_settings_canvas.yview)
        _settings_canvas.configure(yscrollcommand=_settings_scroll.set)
        _settings_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        _settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _settings_inner = ttk.Frame(_settings_canvas)
        _settings_window = _settings_canvas.create_window((0, 0), window=_settings_inner, anchor="nw")

        def _on_settings_configure(event):
            _settings_canvas.configure(scrollregion=_settings_canvas.bbox("all"))
        def _on_canvas_resize(event):
            _settings_canvas.itemconfig(_settings_window, width=event.width)

        _settings_inner.bind("<Configure>", _on_settings_configure)
        _settings_canvas.bind("<Configure>", _on_canvas_resize)

        # Allow mouse-wheel scrolling when the cursor is over the settings tab
        def _on_mousewheel(event):
            _settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        _settings_canvas.bind("<Enter>", lambda e: _settings_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        _settings_canvas.bind("<Leave>", lambda e: _settings_canvas.unbind_all("<MouseWheel>"))
        
        self._build_main_tab(main_frame)
        self._build_settings_tab(_settings_inner)
        
        self.status_var = tk.StringVar(value="Status: Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_main_tab(self, frame):
        engine_frame = ttk.LabelFrame(frame, text="Engine Configuration")
        engine_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.engine_var = tk.StringVar(value=self.engine_path)
        engine_entry = ttk.Entry(engine_frame, textvariable=self.engine_var, state='readonly')
        engine_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        browse_btn = ttk.Button(engine_frame, text="Browse...", command=self.browse_engine)
        browse_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        control_frame = ttk.LabelFrame(frame, text="Controls")
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_detect = ttk.Button(control_frame, text="1. Auto-Detect Chess Board",
                                      command=lambda: threading.Thread(target=self.auto_detect_board_action, daemon=True).start())
        self.btn_detect.pack(fill=tk.X, padx=5, pady=2)

        self.btn_debug_screenshot = ttk.Button(control_frame, text="   Debug: Save Detection Screenshot",
                                               command=lambda: threading.Thread(target=self.save_debug_screenshot, daemon=True).start())
        self.btn_debug_screenshot.pack(fill=tk.X, padx=5, pady=2)
        
        self.chk_flipped = ttk.Checkbutton(control_frame, text="Flipped Board (Black at bottom)", variable=self.flipped_var)
        self.chk_flipped.pack(fill=tk.X, padx=5, pady=2)
        
        self.chk_autoplay = ttk.Checkbutton(control_frame, text="Auto-Play (Simulate Clicks)", variable=self.autoplay_var)
        self.chk_autoplay.pack(fill=tk.X, padx=5, pady=2)
        
        self.btn_white = ttk.Button(control_frame, text="2. Start as White (Alt+W)", command=lambda: self.start_bot("white"))
        self.btn_white.pack(fill=tk.X, padx=5, pady=2)
        
        self.btn_black = ttk.Button(control_frame, text="2. Start as Black (Alt+B)", command=lambda: self.start_bot("black"))
        self.btn_black.pack(fill=tk.X, padx=5, pady=2)
        
        self.btn_stop = ttk.Button(control_frame, text="3. Stop Bot (Alt+X)", command=self.stop_bot, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, padx=5, pady=2)
        
        log_frame = ttk.LabelFrame(frame, text="Activity Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_settings_tab(self, frame):
        engine_settings = ttk.LabelFrame(frame, text="Engine Settings")
        engine_settings.pack(fill=tk.X, padx=10, pady=5)
        engine_settings.columnconfigure(1, weight=1)
        
        # Row 0: Depth
        ttk.Label(engine_settings, text="Thinking Depth (plies):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.depth_entry = ttk.Entry(engine_settings, textvariable=self.depth_var, width=10)
        self.depth_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Row 1: Limit ELO Checkbox
        self.chk_limit_elo = ttk.Checkbutton(engine_settings, text="Limit ELO Strength", variable=self.limit_elo_var)
        self.chk_limit_elo.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W)
        
        # Row 2: ELO Strength Label & Slider
        ttk.Label(engine_settings, text="Bot Strength (ELO):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.elo_label = ttk.Label(engine_settings, text="2000 ELO")
        self.elo_label.grid(row=2, column=2, padx=5, pady=5, sticky=tk.E)
        
        self.elo_slider = ttk.Scale(engine_settings, from_=1350, to=2850, variable=self.elo_var, orient=tk.HORIZONTAL)
        self.elo_slider.grid(row=3, column=0, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        
        # Row 4: Skill Level Slider
        ttk.Label(engine_settings, text="Bot Skill Level (0-20):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        self.skill_label = ttk.Label(engine_settings, text="20")
        self.skill_label.grid(row=4, column=2, padx=5, pady=5, sticky=tk.E)
        
        self.skill_slider = ttk.Scale(engine_settings, from_=0, to=20, variable=self.skill_var, orient=tk.HORIZONTAL)
        self.skill_slider.grid(row=5, column=0, columnspan=3, padx=5, pady=2, sticky=tk.EW)
        
        # Row 6: Threads & Hash
        ttk.Label(engine_settings, text="Threads:").grid(row=6, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(engine_settings, textvariable=self.threads_var, width=10).grid(row=6, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(engine_settings, text="Hash Size (MB):").grid(row=7, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(engine_settings, textvariable=self.hash_var, width=10).grid(row=7, column=1, padx=5, pady=5, sticky=tk.W)

        # Row 8: Analysis mode toggle
        ttk.Separator(engine_settings, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=3, sticky=tk.EW, pady=4)
        self.chk_use_time = ttk.Checkbutton(engine_settings, text="Use Time Limit instead of Depth",
                                            variable=self.use_time_limit_var)
        self.chk_use_time.grid(row=9, column=0, columnspan=3, padx=5, sticky=tk.W)

        ttk.Label(engine_settings, text="Think Time (seconds):").grid(row=10, column=0, padx=5, pady=5, sticky=tk.W)
        self.time_entry = ttk.Entry(engine_settings, textvariable=self.time_limit_var, width=10)
        self.time_entry.grid(row=10, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(engine_settings, text="(0.1 – 10 s recommended)").grid(row=10, column=2, padx=5, sticky=tk.W)

        # Move Display Limits
        limits_frame = ttk.LabelFrame(frame, text="Move Display Limits  (0 = unlimited)")
        limits_frame.pack(fill=tk.X, padx=10, pady=5)
        limits_frame.columnconfigure(1, weight=1)
        limits_frame.columnconfigure(3, weight=1)

        labels_left  = [("Brilliant:", self.max_brilliant_var),
                        ("Great:",     self.max_great_var),
                        ("Best:",      self.max_best_var),
                        ("Excellent:", self.max_excellent_var)]
        labels_right = [("Good:",      self.max_good_var),
                        ("Inaccuracy:",self.max_inaccuracy_var),
                        ("Mistake:",   self.max_mistake_var),
                        ("Blunder:",   self.max_blunder_var)]

        for row_i, ((lbl_l, var_l), (lbl_r, var_r)) in enumerate(zip(labels_left, labels_right)):
            ttk.Label(limits_frame, text=lbl_l).grid(row=row_i, column=0, padx=5, pady=3, sticky=tk.W)
            ttk.Spinbox(limits_frame, from_=0, to=10, textvariable=var_l, width=5).grid(
                row=row_i, column=1, padx=5, pady=3, sticky=tk.W)
            ttk.Label(limits_frame, text=lbl_r).grid(row=row_i, column=2, padx=(15, 5), pady=3, sticky=tk.W)
            ttk.Spinbox(limits_frame, from_=0, to=10, textvariable=var_r, width=5).grid(
                row=row_i, column=3, padx=5, pady=3, sticky=tk.W)

        # Human Engine (Maia / lc0) Frame
        maia_frame = ttk.LabelFrame(frame, text="Human Engine (Maia / lc0)")
        maia_frame.pack(fill=tk.X, padx=10, pady=5)

        self.chk_maia = ttk.Checkbutton(maia_frame, text="Use Maia to choose the move (human-like)",
                                        variable=self.maia_enabled_var)
        self.chk_maia.pack(fill=tk.X, padx=5, pady=(5, 2))

        maia_exe_row = ttk.Frame(maia_frame)
        maia_exe_row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(maia_exe_row, text="lc0.exe:", width=9).pack(side=tk.LEFT)
        ttk.Entry(maia_exe_row, textvariable=self.maia_path_var, state='readonly').pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(maia_exe_row, text="Browse...", command=self.browse_maia_engine).pack(side=tk.RIGHT)

        maia_w_row = ttk.Frame(maia_frame)
        maia_w_row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(maia_w_row, text="Weights:", width=9).pack(side=tk.LEFT)
        ttk.Entry(maia_w_row, textvariable=self.maia_weights_var, state='readonly').pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(maia_w_row, text="Browse...", command=self.browse_maia_weights).pack(side=tk.RIGHT)

        ttk.Label(maia_frame,
                  text="Requires lc0.exe + a maia-*.pb.gz weights file. Pick the rating by the weights file.",
                  foreground="#666666", wraplength=420, justify=tk.LEFT).pack(fill=tk.X, padx=5, pady=(2, 5))

        # Book Frame
        book_frame = ttk.LabelFrame(frame, text="Opening Book Configuration")
        book_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.book_var = tk.StringVar(value="Books/GM.book")
        ttk.Entry(book_frame, textvariable=self.book_var, state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(book_frame, text="Browse...", command=self.browse_book).pack(side=tk.RIGHT, padx=5, pady=5)

        # Coordinates Frame
        coords_frame = ttk.LabelFrame(frame, text="Board Bounding Box (Manual Tuning)")
        coords_frame.pack(fill=tk.X, padx=10, pady=5)

        def make_nudge_row(parent, label, var, row, step=1):
            ttk.Label(parent, text=label).grid(row=row, column=0, padx=5, pady=3, sticky=tk.W)
            ttk.Entry(parent, textvariable=var, width=8).grid(row=row, column=1, padx=2, pady=3)
            ttk.Button(parent, text="−10", width=4,
                       command=lambda v=var, s=step*10: v.set(v.get() - s)).grid(row=row, column=2, padx=1)
            ttk.Button(parent, text="−1", width=4,
                       command=lambda v=var, s=step: v.set(v.get() - s)).grid(row=row, column=3, padx=1)
            ttk.Button(parent, text="+1", width=4,
                       command=lambda v=var, s=step: v.set(v.get() + s)).grid(row=row, column=4, padx=1)
            ttk.Button(parent, text="+10", width=4,
                       command=lambda v=var, s=step*10: v.set(v.get() + s)).grid(row=row, column=5, padx=1)

        make_nudge_row(coords_frame, "Board X (px):",    self.board_x_var,    row=0)
        make_nudge_row(coords_frame, "Board Y (px):",    self.board_y_var,    row=1)
        make_nudge_row(coords_frame, "Board Size (px):", self.board_size_var, row=2)

        self.btn_bbox_preview = ttk.Button(coords_frame, text="👁 Show Box on Screen",
                                           command=self.toggle_bbox_preview)
        self.btn_bbox_preview.grid(row=3, column=0, columnspan=6, padx=5, pady=6, sticky=tk.EW)

    def log(self, message):
        if threading.current_thread() is threading.main_thread():
            self._log_impl(message)
        else:
            self.root.after(0, self._log_impl, message)

    def _log_impl(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def browse_engine(self):
        path = filedialog.askopenfilename(title="Select Engine Executable", filetypes=[("Executables", "*.exe")])
        if path:
            self.engine_path = path
            self.engine_var.set(path)
            self.log(f"Engine path updated: {path}")
            self.save_config()

    def browse_maia_engine(self):
        path = filedialog.askopenfilename(title="Select lc0 Executable", filetypes=[("Executables", "*.exe")])
        if path:
            self.maia_path_var.set(path)
            self.log(f"Maia (lc0) path updated: {path}")
            self.save_config()

    def browse_maia_weights(self):
        path = filedialog.askopenfilename(
            title="Select Maia Weights",
            filetypes=[("Weights", "*.pb.gz;*.pb;*.gz"), ("All files", "*.*")])
        if path:
            self.maia_weights_var.set(path)
            self.log(f"Maia weights updated: {os.path.basename(path)}")
            self.save_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                import json
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                
                # Load engine path
                if "engine_path" in config and os.path.exists(config["engine_path"]):
                    self.engine_path = config["engine_path"]
                    self.engine_var.set(self.engine_path)
                    
                # Load book path
                if "book_path" in config and os.path.exists(config["book_path"]):
                    self.book_path = config["book_path"]
                    self.book_var.set(self.book_path)
                    self.load_book()
                    
                # Load depth settings
                if "depth" in config:
                    self.depth_var.set(config["depth"])
                if "limit_elo" in config:
                    self.limit_elo_var.set(config["limit_elo"])
                if "elo" in config:
                    self.elo_var.set(config["elo"])
                if "skill_level" in config:
                    self.skill_var.set(config["skill_level"])
                if "threads" in config:
                    self.threads_var.set(config["threads"])
                if "hash" in config:
                    self.hash_var.set(config["hash"])
                if "use_time_limit" in config:
                    self.use_time_limit_var.set(config["use_time_limit"])
                if "time_limit" in config:
                    self.time_limit_var.set(float(config["time_limit"]))
                if "max_brilliant" in config:
                    self.max_brilliant_var.set(config["max_brilliant"])
                if "max_great" in config:
                    self.max_great_var.set(config["max_great"])
                if "max_best" in config:
                    self.max_best_var.set(config["max_best"])
                if "max_excellent" in config:
                    self.max_excellent_var.set(config["max_excellent"])
                if "max_good" in config:
                    self.max_good_var.set(config["max_good"])
                if "max_inaccuracy" in config:
                    self.max_inaccuracy_var.set(config["max_inaccuracy"])
                if "max_mistake" in config:
                    self.max_mistake_var.set(config["max_mistake"])
                if "max_blunder" in config:
                    self.max_blunder_var.set(config["max_blunder"])

                # Load coordinates if they exist
                if "board_x" in config:
                    self.board_x_var.set(config["board_x"])
                if "board_y" in config:
                    self.board_y_var.set(config["board_y"])
                if "board_size" in config:
                    self.board_size_var.set(config["board_size"])
                if "flipped" in config:
                    self.flipped_var.set(config["flipped"])
                if "autoplay" in config:
                    self.autoplay_var.set(config["autoplay"])

                # Load Maia (lc0) settings
                if "maia_enabled" in config:
                    self.maia_enabled_var.set(config["maia_enabled"])
                if "maia_path" in config and config["maia_path"]:
                    self.maia_path_var.set(config["maia_path"])
                if "maia_weights" in config and config["maia_weights"]:
                    self.maia_weights_var.set(config["maia_weights"])

                self.log("Configuration loaded successfully.")
        except Exception as e:
            self.log(f"Error loading configuration: {e}")

    def save_config(self, *args):
        try:
            import json
            
            # Helper to get IntVars safely during user typing
            def safe_get_int(var, default_val):
                try:
                    return var.get()
                except Exception:
                    return default_val
                    
            # Helper to get BooleanVars safely
            def safe_get_bool(var, default_val):
                try:
                    return var.get()
                except Exception:
                    return default_val
                    
            def safe_get_float(var, default_val):
                try:
                    return float(var.get())
                except Exception:
                    return default_val

            config = {
                "engine_path": self.engine_path,
                "book_path": self.book_path,
                "depth": safe_get_int(self.depth_var, 15),
                "limit_elo": safe_get_bool(self.limit_elo_var, False),
                "elo": safe_get_int(self.elo_var, 2000),
                "skill_level": safe_get_int(self.skill_var, 20),
                "threads": safe_get_int(self.threads_var, 1),
                "hash": safe_get_int(self.hash_var, 16),
                "use_time_limit": safe_get_bool(self.use_time_limit_var, False),
                "time_limit": safe_get_float(self.time_limit_var, 1.0),
                "max_brilliant": safe_get_int(self.max_brilliant_var, 1),
                "max_great": safe_get_int(self.max_great_var, 1),
                "max_best": safe_get_int(self.max_best_var, 3),
                "max_excellent": safe_get_int(self.max_excellent_var, 3),
                "max_good": safe_get_int(self.max_good_var, 3),
                "max_inaccuracy": safe_get_int(self.max_inaccuracy_var, 1),
                "max_mistake": safe_get_int(self.max_mistake_var, 1),
                "max_blunder": safe_get_int(self.max_blunder_var, 1),
                "board_x": safe_get_int(self.board_x_var, 0),
                "board_y": safe_get_int(self.board_y_var, 0),
                "board_size": safe_get_int(self.board_size_var, 0),
                "flipped": safe_get_bool(self.flipped_var, False),
                "autoplay": safe_get_bool(self.autoplay_var, False),
                "maia_enabled": safe_get_bool(self.maia_enabled_var, False),
                "maia_path": self.maia_path_var.get(),
                "maia_weights": self.maia_weights_var.get()
            }
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def update_board_from_settings(self, *args):
        try:
            x = self.board_x_var.get()
            y = self.board_y_var.get()
            w = self.board_size_var.get()
            if w > 0:
                self.board_bbox = (x, y, w, w)
                self.sq_size = w // 8

                if self.overlay:
                    self.overlay.x = x
                    self.overlay.y = y
                    self.overlay.size = w
                    self.overlay.sq_size = w // 8
                    self.overlay.win.geometry(f"{w}x{w}+{x}+{y}")
                    self.overlay.canvas.config(width=w, height=w)

                if self.bbox_preview:
                    self.bbox_preview.update(x, y, w, w // 8)

                self.save_config()
        except Exception:
            pass

    def toggle_bbox_preview(self):
        if self.bbox_preview:
            # Hide: destroy the overlay and reset button label
            self.bbox_preview.destroy()
            self.bbox_preview = None
            self.btn_bbox_preview.config(text="👁 Show Box on Screen")
        else:
            # Show: require a valid bbox first
            if not self.board_bbox or self.board_bbox[2] == 0:
                messagebox.showwarning("No bbox", "Run Auto-Detect first (or set Board X/Y/Size manually).")
                return
            x, y, w, _ = self.board_bbox
            sq = w // 8
            self.bbox_preview = BboxPreviewOverlay(self.root, x, y, w, sq)
            self.btn_bbox_preview.config(text="👁 Hide Box on Screen")

    def browse_book(self):
        path = filedialog.askopenfilename(
            title="Select Opening Book", 
            filetypes=[("All supported books", "*.book;*.bin"), ("Custom book files", "*.book"), ("Polyglot book files", "*.bin"), ("All files", "*.*")]
        )
        if path:
            self.book_path = path
            self.book_var.set(path)
            self.load_book()
            self.save_config()

    def load_book(self):
        self.book_lines = []
        if not os.path.exists(self.book_path):
            alt_path = os.path.join(self.script_dir, "Books", os.path.basename(self.book_path))
            if os.path.exists(alt_path):
                self.book_path = alt_path
            else:
                self.log(f"Warning: Opening book not found at '{self.book_path}'. Fallback to engine.")
                return False
        
        # Check if Polyglot book
        if self.book_path.lower().endswith(".bin"):
            try:
                import chess.polyglot
                with chess.polyglot.open_reader(self.book_path) as reader:
                    # Validate book has entries for the starting position
                    start_entries = list(reader.find_all(chess.Board()))
                    if not start_entries:
                        self.log("Warning: Polyglot book has 0 entries for the starting position.")
                self.log(f"Polyglot opening book loaded: {os.path.basename(self.book_path)}")
                return True
            except Exception as e:
                self.log(f"Warning: Failed to load Polyglot book: {e}")
                return False
        else:
            try:
                self.log(f"Loading opening book {os.path.basename(self.book_path)}...")
                with open(self.book_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.read().splitlines()
                
                if not lines or lines[0].strip() != "ChessBotBook":
                    self.log("Warning: Invalid book header. Expected 'ChessBotBook'.")
                    return False
                    
                parsed = []
                for line in lines[2:]:
                    line = line.strip()
                    if line:
                        moves = line.split()
                        if moves:
                            parsed.append(moves)
                self.book_lines = parsed
                self.log(f"Loaded {len(self.book_lines)} book lines successfully.")
                return True
            except Exception as e:
                self.log(f"Warning: Failed to load opening book: {e}")
                return False

    def get_book_moves(self):
        # 1. Polyglot book check
        if self.book_path.lower().endswith(".bin"):
            try:
                import chess.polyglot
                if os.path.exists(self.book_path):
                    with chess.polyglot.open_reader(self.book_path) as reader:
                        entries = reader.find_all(self.game_board)
                        entries = sorted(entries, key=lambda x: x.weight, reverse=True)
                        return [entry.move().uci() for entry in entries[:5]]
            except Exception:
                pass
            return []
            
        # 2. Custom ChessBotBook text format check
        if not self.book_lines:
            return []
            
        played_moves = [move.uci() for move in self.game_board.move_stack]
        depth = len(played_moves)
        
        candidates = []
        for line in self.book_lines:
            if len(line) > depth:
                if line[:depth] == played_moves:
                    candidates.append(line[depth])
                    
        if not candidates:
            return []
            
        from collections import Counter
        counts = Counter(candidates)
        # Deduplicate and sort by count descending
        sorted_moves = [move for move, count in counts.most_common(5)]
        return sorted_moves

    def init_engine(self):
        if self.engine:
            try:
                # Ping the engine to verify it's still alive
                self.engine.ping()
                return True
            except Exception:
                self.log("Engine process died, re-initializing...")
                self.engine = None
        if not os.path.exists(self.engine_path):
            messagebox.showerror("Error", "Engine not found! Browse for Stockfish.exe.")
            return False
        try:
            self.log(f"Initializing engine {os.path.basename(self.engine_path)}...")
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self._apply_engine_settings()
            self.log("Engine loaded successfully.")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load engine:\n{e}")
            return False

    def init_maia_engine(self):
        """Launch the lc0/Maia engine used to pick human-like moves. Returns True on success.

        Never raises: on any failure it logs a warning and returns False so the bot can
        fall back to Stockfish-only move selection.
        """
        if self.maia_engine:
            try:
                self.maia_engine.ping()
                return True
            except Exception:
                self.log("Maia process died, re-initializing...")
                self.maia_engine = None

        lc0_path = self.maia_path_var.get()
        weights_path = self.maia_weights_var.get()
        if not lc0_path or not os.path.exists(lc0_path):
            self.log(f"Warning: lc0 executable not found at '{lc0_path}'. Maia disabled for this run.")
            return False
        if not weights_path or not os.path.exists(weights_path):
            self.log(f"Warning: Maia weights not found at '{weights_path}'. Maia disabled for this run.")
            return False

        try:
            self.log(f"Initializing Maia (lc0) with {os.path.basename(weights_path)}...")
            self.maia_engine = chess.engine.SimpleEngine.popen_uci(
                [lc0_path, f"--weights={weights_path}"])
            # Init uses the default 10s timeout (loading the NN can be slow). Per-move
            # queries are tiny, so tighten the timeout afterwards to fail fast instead
            # of letting an unresponsive engine stall the think loop.
            self.maia_engine.timeout = 5.0
            self.maia_fail_count = 0
            self.log("Maia engine loaded successfully.")
            return True
        except Exception as e:
            self.log(f"Warning: Failed to load Maia engine: {e}. Continuing with Stockfish only.")
            self.maia_engine = None
            return False

    def get_maia_move(self, board):
        """Return Maia's most-likely human move (lc0 policy at nodes=1), or None.

        The limit carries an explicit ``time`` ceiling: python-chess only applies a
        wall-clock timeout when ``Limit.time`` is set, so a bare ``nodes=1`` limit would
        let an unresponsive lc0 hang the worker thread forever (leaving ``is_thinking``
        stuck True and freezing the overlay). After repeated failures Maia is disabled
        for the session so the bot keeps running on Stockfish.
        """
        if not self.maia_engine:
            return None
        try:
            result = self.maia_engine.play(board, chess.engine.Limit(nodes=1, time=2.0))
            self.maia_fail_count = 0
            return result.move
        except Exception as e:
            self.maia_fail_count = getattr(self, "maia_fail_count", 0) + 1
            self.log(f"Maia move error ({self.maia_fail_count}/3): {e}")
            if self.maia_fail_count >= 3:
                self.log("Maia unresponsive - disabling it for this session, using Stockfish only.")
                try:
                    self.maia_engine.quit()
                except Exception:
                    pass
                self.maia_engine = None
            return None

    def _format_eval(self, pov_score):
        """Format a python-chess PovScore as a short +/- string from the side-to-move's view.

        Positive always means good for the player to move (e.g. '+1.5', '-0.3', '+M3').
        """
        try:
            rel = pov_score.relative
            if rel.is_mate():
                m = rel.mate()
                if m is None:
                    return ""
                return f"+M{abs(m)}" if m > 0 else f"-M{abs(m)}"
            cp = rel.score()
            if cp is None:
                return ""
            return f"{cp / 100.0:+.1f}"
        except Exception:
            return ""

    def _apply_engine_settings(self):
        """Apply ELO, Skill Level, Threads, and Hash limit options to the running engine."""
        if not self.engine:
            return
        try:
            limit_elo = bool(self.limit_elo_var.get())
            elo = int(self.elo_var.get())
            skill = int(self.skill_var.get())
            threads = int(self.threads_var.get())
            hash_size = int(self.hash_var.get())
        except Exception:
            limit_elo = False
            elo = 2000
            skill = 20
            threads = 1
            hash_size = 16
            
        try:
            options = {
                "Threads": threads,
                "Hash": hash_size
            }
            if limit_elo:
                options["UCI_LimitStrength"] = True
                options["UCI_Elo"] = elo
                self.log(f"Engine options: Threads={threads}, Hash={hash_size}MB, Strength={elo} ELO.")
            else:
                options["UCI_LimitStrength"] = False
                options["Skill Level"] = skill
                self.log(f"Engine options: Threads={threads}, Hash={hash_size}MB, Skill Level={skill}.")
                
            self.engine.configure(options)
        except Exception as e:
            self.log(f"Warning: Could not configure engine: {e}")

    def _update_strength_ui(self, *args):
        """Called when any strength-related variable changes. Toggles slider states and updates labels."""
        try:
            limit_elo = self.limit_elo_var.get()
        except Exception:
            limit_elo = False
            
        if limit_elo:
            try:
                self.elo_slider.state(['!disabled'])
                self.skill_slider.state(['disabled'])
            except Exception:
                pass
            try:
                elo_val = int(self.elo_var.get())
                self.elo_label.config(text=f"{elo_val} ELO")
            except Exception:
                pass
        else:
            try:
                self.elo_slider.state(['disabled'])
                self.skill_slider.state(['!disabled'])
            except Exception:
                pass
            try:
                self.elo_label.config(text="Full Strength (Disabled)")
            except Exception:
                pass
                
        try:
            skill_val = int(self.skill_var.get())
            self.skill_label.config(text=str(skill_val))
        except Exception:
            pass
            
        self._apply_engine_settings()
        self.save_config()

    def _update_analysis_mode_ui(self, *args):
        """Enable/disable depth vs time entries based on the toggle."""
        try:
            use_time = self.use_time_limit_var.get()
        except Exception:
            use_time = False
        try:
            if use_time:
                self.depth_entry.state(['disabled'])
                self.time_entry.state(['!disabled'])
            else:
                self.depth_entry.state(['!disabled'])
                self.time_entry.state(['disabled'])
        except Exception:
            pass
        self.save_config()

    def _get_label_limit(self, label):
        """Return the max display count for a label type. 0 means unlimited."""
        mapping = {
            "Brilliant": self.max_brilliant_var,
            "Great":     self.max_great_var,
            "Best":      self.max_best_var,
            "Excellent": self.max_excellent_var,
            "Good":      self.max_good_var,
            "Inaccuracy":self.max_inaccuracy_var,
            "Mistake":   self.max_mistake_var,
            "Blunder":   self.max_blunder_var,
            "Miss":      self.max_blunder_var,
        }
        var = mapping.get(label)
        if var is None:
            return 0
        try:
            return max(0, var.get())
        except Exception:
            return 0

    def is_sacrifice(self, board, move):
        """Returns True if the move sacrifices material and doesn't immediately regain equal/greater value."""
        try:
            b = board.copy()
            moving_piece = b.piece_at(move.from_square)
            if not moving_piece or moving_piece.piece_type == chess.KING:
                return False
                
            piece_values = {
                chess.PAWN: 100,
                chess.KNIGHT: 300,
                chess.BISHOP: 300,
                chess.ROOK: 500,
                chess.QUEEN: 900
            }
            val_moving = piece_values.get(moving_piece.piece_type, 100)
            
            # Check if it captures a piece of equal or higher value
            captured = b.piece_at(move.to_square)
            if captured:
                val_captured = piece_values.get(captured.piece_type, 0)
                if val_captured >= val_moving:
                    return False
                    
            # Make the move
            b.push(move)
            # Check if the moved piece can be captured by a lower value piece on the next turn
            opp_color = b.turn
            attackers = b.attackers(opp_color, move.to_square)
            for sq in attackers:
                attacker_piece = b.piece_at(sq)
                if attacker_piece and attacker_piece.piece_type != chess.KING:
                    val_attacker = piece_values.get(attacker_piece.piece_type, 100)
                    if val_attacker < val_moving:
                        return True
        except Exception:
            pass
        return False

    def classify_move(self, board, move, score, best_score, second_best_score, book_moves):
        """Classifies a move based on centipawn loss and tactical details, returning (type, hex_color)."""
        try:
            move_uci = move.uci()
            if book_moves and move_uci in book_moves:
                return "Book", "#d5a478" # Brown/Tan
                
            loss = best_score - score
            
            # Check Miss (missing a huge winning opportunity)
            if best_score >= 300 and score < 100 and loss >= 200:
                return "Miss", "#fa5353" # Coral Red / Pinkish Red
                
            # Check Blunder
            if loss > 200:
                return "Blunder", "#d12a2a" # Deep Red
                
            # Check Mistake
            if loss > 90:
                return "Mistake", "#f5952f" # Orange
                
            # Check Inaccuracy
            if loss >= 50:
                return "Inaccuracy", "#f5c400" # Yellow
                
            # Check Brilliant (sacrifice that maintains position or is good)
            if loss <= 20 and self.is_sacrifice(board, move):
                return "Brilliant", "#12b497" # Turquoise / Bright Teal
                
            # Check Great (only saving/winning move — only when not already losing and gap is decisive)
            if loss == 0 and second_best_score is not None and best_score > -100:
                second_best_loss = best_score - second_best_score
                if second_best_loss >= 200:
                    return "Great", "#5c8bb0" # Slate Blue
                    
            # Standard classifications
            if loss == 0:
                return "Best", "#81b64c" # Apple Green
            elif loss <= 20:
                return "Excellent", "#81b64c" # Apple Green (Excellent and Best use the same green)
            else:
                return "Good", "#7fa650" # Faded/Olive Green
        except Exception:
            return "Good", "#7fa650"


    def load_model(self):
        """Lazy load PyTorch and our trained CNN model."""
        if self.model is not None:
            return True
            
        model_path = os.path.join(self.script_dir, "chess_piece_model.pth")
        if not os.path.exists(model_path):
            messagebox.showerror("Model Error", "Trained model 'chess_piece_model.pth' not found.\n\nPlease collect data and train the model first!")
            return False
            
        try:
            self.log("Loading PyTorch and Neural Network...")
            import torch
            import torchvision.transforms as transforms
            from PIL import Image
            
            self.torch = torch
            self.transforms = transforms
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            # Recreate model structure
            import torch.nn as nn
            class ChessPieceCNN(nn.Module):
                def __init__(self, num_classes=13):
                    super(ChessPieceCNN, self).__init__()
                    self.features = nn.Sequential(
                        nn.Conv2d(3, 16, kernel_size=3, padding=1),
                        nn.BatchNorm2d(16),
                        nn.ReLU(),
                        nn.MaxPool2d(2, 2), # 32x32
                        
                        nn.Conv2d(16, 32, kernel_size=3, padding=1),
                        nn.BatchNorm2d(32),
                        nn.ReLU(),
                        nn.MaxPool2d(2, 2), # 16x16
                        
                        nn.Conv2d(32, 64, kernel_size=3, padding=1),
                        nn.BatchNorm2d(64),
                        nn.ReLU(),
                        nn.MaxPool2d(2, 2)  # 8x8
                    )
                    self.classifier = nn.Sequential(
                        nn.Linear(64 * 8 * 8, 128),
                        nn.ReLU(),
                        nn.Dropout(0.3),
                        nn.Linear(128, num_classes)
                    )
                    
                def forward(self, x):
                    x = self.features(x)
                    x = x.view(x.size(0), -1)
                    x = self.classifier(x)
                    return x
            
            self.model = ChessPieceCNN(num_classes=13)
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.to(self.device)
            self.model.eval()
            
            self.log(f"Model loaded successfully on {self.device}!")
            return True
        except Exception as e:
            messagebox.showerror("Error Loading Model", f"Could not load neural network: {e}")
            return False

    def auto_detect_board_action(self):
        self.log("Scanning screen for chess board...")
        bbox = self.auto_detect_board()
        if bbox:
            # Schedule all Tkinter widget updates on the main thread
            def _apply():
                self.board_x_var.set(bbox[0])
                self.board_y_var.set(bbox[1])
                self.board_size_var.set(bbox[2])
                self.btn_detect.config(text="1. Auto-Detect Chess Board (Done)")
            self.root.after(0, _apply)
            self.log(f"Board detected! x={bbox[0]}, y={bbox[1]}, size={bbox[2]}px (sq={bbox[4]}px)")
        else:
            self.log("ERROR: Chess board not found on screen!")
            self.root.after(0, lambda: messagebox.showerror("Error", "Could not find a chess board on screen. Ensure the board is fully visible."))

    def save_debug_screenshot(self):
        """Take a screenshot, draw the detected board bbox on it, and save to disk for diagnosis."""
        import os
        self.log("Saving debug detection screenshot...")
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = np.array(sct.grab(monitor))
            bgr = screenshot[:, :, :3].copy()

            bbox = self.auto_detect_board()
            if bbox:
                x, y, w, h, sq = bbox
                # Draw the detected board rectangle in bright green
                cv2.rectangle(bgr, (x, y), (x + w, y + h), (0, 255, 0), 3)
                # Draw individual square grid lines in yellow
                for i in range(9):
                    cv2.line(bgr, (x + i * sq, y), (x + i * sq, y + h), (0, 255, 255), 1)
                    cv2.line(bgr, (x, y + i * sq), (x + w, y + i * sq), (0, 255, 255), 1)
                label = f"Detected: x={x} y={y} size={w} sq={sq}"
                cv2.putText(bgr, label, (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                self.log(f"Debug: {label}")
            else:
                cv2.putText(bgr, "NO BOARD DETECTED", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)
                self.log("Debug: No board detected in screenshot.")

            # Also draw the currently stored bbox in blue for comparison
            try:
                sx, sy, sw, sh = self.board_bbox
                cv2.rectangle(bgr, (sx, sy), (sx + sw, sy + sh), (255, 0, 0), 2)
                cv2.putText(bgr, f"Stored: x={sx} y={sy} size={sw}", (sx, sy + sh + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            except Exception:
                pass

            out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_detection.png")
            cv2.imwrite(out_path, bgr)
            self.log(f"Debug screenshot saved: {out_path}")
            self.root.after(0, lambda: messagebox.showinfo("Debug Screenshot", f"Saved to:\n{out_path}"))
        except Exception as e:
            self.log(f"Debug screenshot error: {e}")

    def find_board_in_row(self, row_bgr, width):
        row = row_bgr.astype(np.int16)
        diffs = np.sqrt(np.sum((row[1:].astype(float) - row[:-1].astype(float))**2, axis=1))
        trans = np.where(diffs > 25)[0]
        if len(trans) < 7:
            return None
        merged = [trans[0]]
        for t in trans[1:]:
            if t - merged[-1] > 5:
                merged.append(t)
        if len(merged) < 7:
            return None
            
        for i in range(len(merged) - 6):
            bounds = merged[i:i+7]
            gaps = [bounds[j+1] - bounds[j] for j in range(6)]
            avg = sum(gaps) / 6
            if avg < 40 or avg > 300:
                continue
            if not all(abs(g - avg) < avg * 0.12 for g in gaps):
                continue
                
            sq_size = int(round(avg))
            best_x_start = bounds[0] - sq_size
            best_score = -1
            
            for offset in [0, 1, 2]:
                x_cand = bounds[0] - offset * sq_size
                if x_cand < 0 or x_cand + 8 * sq_size >= width:
                    continue
                
                score = 0
                tol = max(5, int(0.08 * sq_size))
                for step in range(9):
                    target_x = x_cand + step * sq_size
                    if any(abs(m - target_x) <= tol for m in merged):
                        score += 1
                if score > best_score:
                    best_score = score
                    best_x_start = x_cand
                    
            return (best_x_start, sq_size)
            
        return None

    def auto_detect_board(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = np.array(sct.grab(monitor))
        screen_h, screen_w = screenshot.shape[:2]
        self.log(f"Debug Screen: physical={screen_w}x{screen_h}, logical={monitor['width']}x{monitor['height']}")
        bgr = screenshot[:, :, :3]
        
        row_hits = []
        for y in range(0, screen_h, 3):
            result = self.find_board_in_row(bgr[y], screen_w)
            if result:
                row_hits.append((y, result[0], result[1]))
                
        if len(row_hits) < 10:
            return None
            
        groups = []
        current = [row_hits[0]]
        for hit in row_hits[1:]:
            prev = current[-1]
            if abs(hit[1] - prev[1]) < 10 and abs(hit[2] - prev[2]) < 5 and hit[0] - prev[0] < 15:
                current.append(hit)
            else:
                if len(current) >= 10:
                    groups.append(current)
                current = [hit]
        if len(current) >= 10:
            groups.append(current)
            
        if not groups:
            return None
            
        best = max(groups, key=len)
        x_start = int(np.median([h[1] for h in best]))
        sq_size = int(np.median([h[2] for h in best]))
        board_size = sq_size * 8
        
        # Grid alignment vertical refinement
        # Set the rough top of the board to the first detected row hit in the group
        y_rough = best[0][0]
        self.log(f"Debug: y_first={best[0][0]}, y_last={best[-1][0]}, sq={sq_size}, size={board_size}")
        
        # Sample 4 columns near the middle of the board (at column centers)
        cols_x = [x_start + int(sq_size * (i + 0.5)) for i in range(2, 6)]
        
        # The true top of the board could be up to 7 squares above y_rough
        y_min = max(0, y_rough - 8 * sq_size)
        y_max = min(screen_h - 1, y_rough + board_size + 8 * sq_size)
        
        grads = np.zeros(y_max - y_min)
        for col_x in cols_x:
            col_x = min(max(0, col_x), screen_w - 1)
            col_pixels = bgr[y_min:y_max, col_x].astype(float)
            col_diffs = np.mean(np.abs(col_pixels[1:] - col_pixels[:-1]), axis=1)
            grads[:len(col_diffs)] += col_diffs
            
        best_y_start = y_rough
        best_grad_sum = -1

        # Search for the optimal offset (in squares) and fine-tuning (dy in pixels)
        # Search both above (-8..0) and below (0..+1) y_rough to handle boards where
        # y_rough lands inside the board rather than at the top edge
        for offset in range(-1, 9):
            for dy in range(-sq_size // 2, sq_size // 2):
                y_start_cand = y_rough - offset * sq_size + dy
                if y_start_cand < 0 or y_start_cand + board_size >= screen_h:
                    continue
                    
                # Sum gradients at the 9 horizontal grid lines
                grad_sum = 0
                for step in range(9):
                    grid_y = y_start_cand + step * sq_size
                    idx = int(round(grid_y)) - y_min
                    if 0 <= idx < len(grads):
                        grad_sum += grads[idx]
                        
                if grad_sum > best_grad_sum:
                    best_grad_sum = grad_sum
                    best_y_start = y_start_cand
                    
        y_start_refined = max(0, best_y_start)
        return (x_start, y_start_refined, board_size, board_size, sq_size)

    def read_board(self, flipped=False):
        x, y, w, h = self.board_bbox
        sq = self.sq_size
        
        with mss.mss() as sct:
            monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
            img = np.array(sct.grab(monitor))[:, :, :3]  # BGR
            
        # Transform for model
        eval_transform = self.transforms.Compose([
            self.transforms.Resize((64, 64)),
            self.transforms.ToTensor(),
            self.transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
        from PIL import Image
        
        # Batch preparation (determine square sizes directly from the captured image dimensions to prevent scaling mismatches)
        img_h, img_w = img.shape[:2]
        sq_w = img_w / 8.0
        sq_h = img_h / 8.0
        
        squares = []
        for row in range(8):
            for col in range(8):
                y1 = int(round(row * sq_h))
                y2 = int(round((row + 1) * sq_h))
                x1 = int(round(col * sq_w))
                x2 = int(round((col + 1) * sq_w))
                
                cell_img = img[y1:y2, x1:x2]
                cell_img_rgb = cv2.cvtColor(cell_img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(cell_img_rgb)
                squares.append(eval_transform(pil_img))
                
        # Stack all 64 squares into a single batch
        batch = self.torch.stack(squares).to(self.device)
        
        with self.torch.no_grad():
            outputs = self.model(batch)
            _, predictions = outputs.max(1)
            predictions = predictions.cpu().numpy()
            raw_logits = outputs.cpu().numpy()
            
        board = []
        for r in range(8):
            board_row = []
            for c in range(8):
                if flipped:
                    row = 7 - r
                    col = 7 - c
                else:
                    row = r
                    col = c
                
                pred_idx = predictions[row * 8 + col]
                label = CLASSES[pred_idx]
                
                if label == 'empty':
                    board_row.append(None)
                else:
                    # Parse piece: e.g. 'wp' -> 'P', 'bp' -> 'p'
                    piece_color = label[0]
                    piece_type = label[1]
                    board_row.append(piece_type.upper() if piece_color == 'w' else piece_type)
            board.append(board_row)
            
        # Temporal filtering: majority vote over last 3 frames to filter out movement/highlight noise
        self.board_history.append(board)
        if len(self.board_history) > 3:
            self.board_history.pop(0)
            
        if len(self.board_history) == 3:
            from collections import Counter
            voted_board = []
            for r in range(8):
                voted_row = []
                for c in range(8):
                    votes = [self.board_history[i][r][c] for i in range(3)]
                    most_common = Counter(votes).most_common(1)[0][0]
                    voted_row.append(most_common)
                voted_board.append(voted_row)
            board = voted_board
            
        # Sanity check: Ensure both kings exist
        flat = [piece for r in board for piece in r]
        
        if 'K' not in flat:
            wk_logits = raw_logits[:, 6]
            for idx in np.argsort(wk_logits)[::-1]:
                row, col = idx // 8, idx % 8
                r_fen = 7 - row if flipped else row
                c_fen = 7 - col if flipped else col
                if board[r_fen][c_fen] != 'k':
                    board[r_fen][c_fen] = 'K'
                    print(f"Sanity Check: Recovered missing White King at FEN row {r_fen}, col {c_fen}")
                    break
            # Rebuild flat list after potential board modification
            flat = [piece for r in board for piece in r]
            
        if 'k' not in flat:
            bk_logits = raw_logits[:, 12]
            for idx in np.argsort(bk_logits)[::-1]:
                row, col = idx // 8, idx % 8
                r_fen = 7 - row if flipped else row
                c_fen = 7 - col if flipped else col
                if board[r_fen][c_fen] != 'K':
                    board[r_fen][c_fen] = 'k'
                    print(f"Sanity Check: Recovered missing Black King at FEN row {r_fen}, col {c_fen}")
                    break
            
        fen = ""
        for r, row in enumerate(board):
            empty = 0
            for piece in row:
                if piece is None:
                    empty += 1
                else:
                    # Promote invalid pawns on the 1st and 8th rank to Queens (row 0 = rank 8, row 7 = rank 1)
                    if piece.upper() == 'P' and (r == 0 or r == 7):
                        piece = 'Q' if piece.isupper() else 'q'
                        
                    if empty > 0:
                        fen += str(empty)
                        empty = 0
                    fen += piece
            if empty > 0:
                fen += str(empty)
            fen += "/"
        return board, fen[:-1]

    def sync_board(self, board_fen, color):
        primary = "w" if color == "white" else "b"
        opposite = "b" if primary == "w" else "w"
        
        # Try to find a valid FEN configuration to initialize/repair our tracked board
        reasons = []
        for turn in [primary, opposite]:
            for castling in ["KQkq", "-"]:
                full_fen = f"{board_fen} {turn} {castling} - 0 1"
                try:
                    b = chess.Board(full_fen)
                    if b.is_valid():
                        self.game_board = b
                        self.current_turn = "white" if turn == "w" else "black"
                        return
                    else:
                        # Check status of board
                        reasons.append(f"is_valid=False for {full_fen}")
                except ValueError as ve:
                    reasons.append(f"ValueError for {full_fen}: {ve}")
                    continue
                    
        if reasons:
            self.log(f"FEN Sync Failed: {reasons[0]}")
                    
        # Fallback if nothing is valid: DO NOT overwrite if game_board already exists
        if hasattr(self, 'game_board') and self.game_board is not None:
            self.log("Warning: Screen board is invalid. Keeping previous game board state.")
            return
            
        # First-time fallback: use a simple 2-king valid board with turn matching player color
        turn_char = "w" if color == "white" else "b"
        self.game_board = chess.Board(f"k7/8/8/8/8/8/8/K7 {turn_char} - - 0 1")
        self.current_turn = color

    def start_bot(self, color):
        if not self.board_bbox:
            messagebox.showwarning("Warning", "Please auto-detect the board first!")
            return
        if not self.load_model():
            return
        if not self.init_engine():
            return

        # Optionally start the Maia (lc0) human engine. Failure is non-fatal: the bot
        # continues with Stockfish-only move selection.
        if self.maia_enabled_var.get():
            if not self.init_maia_engine():
                self.log("Maia unavailable - using Stockfish for move choice this run.")

        # Lazy load book lines if not already loaded
        if not self.book_lines:
            self.load_book()
            
        # Create visual overlay over the detected board
        x, y, w, h = self.board_bbox
        self.overlay = MoveOverlay(self.root, x, y, w, self.sq_size)
        
        # Auto-set flipped state based on color choice, but user can override it
        self.flipped_var.set(color == "black")
        
        # Read the current board and sync game state
        try:
            _, board_fen = self.read_board(flipped=self.flipped_var.get())
            self.sync_board(board_fen, color)
        except Exception:
            self.game_board = chess.Board()
            self.current_turn = color
            
        self.board_history = []
        self.desync_count = 0
        self.maia_fail_count = 0
        self.is_thinking = False # Flag to track background Stockfish calculations
        self.is_running = True
        self.last_clicked_fen = ""
        self.status_var.set(f"Status: Playing as {color.capitalize()}")
        self.log(f"Started playing as {color.capitalize()}.")
        
        self.btn_white.config(state=tk.DISABLED)
        self.btn_black.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        threading.Thread(target=self.bot_loop, args=(color,), daemon=True).start()

    def bot_loop(self, color):
        last_board_fen = ""
        last_calculated_fen = ""
        
        while self.is_running:
            if getattr(self, 'is_moving_mouse', False):
                time.sleep(0.05)
                continue
            try:
                is_flipped = self.flipped_var.get()
                board_grid, board_fen = self.read_board(flipped=is_flipped)
                
                # Check if board representation changed
                if board_fen != last_board_fen:
                    last_board_fen = board_fen
                    self.log(f"Detected Board: {board_fen}")
                    
                    # Check if board matches our current tracked state
                    if board_fen == self.game_board.board_fen():
                        self.desync_count = 0
                    else:
                        # Try to find a legal move that transitions to the new FEN
                        move_found = None
                        for move in self.game_board.legal_moves:
                            self.game_board.push(move)
                            sim_fen = self.game_board.board_fen()
                            self.game_board.pop()
                            if sim_fen == board_fen:
                                move_found = move
                                break
                                
                        if move_found:
                            self.game_board.push(move_found)
                            self.current_turn = "white" if self.game_board.turn == chess.WHITE else "black"
                            self.desync_count = 0
                            self.log(f"Detected Move: {move_found.uci()}")
                        else:
                            # Not matching any legal move, increment desync count (could be transient noise)
                            self.desync_count += 1
                            if self.desync_count >= 3: # Reduced from 5 to 3 for much faster detection
                                # Re-sync with the current camera view
                                self.sync_board(board_fen, color)
                                self.desync_count = 0
                                
                    # Update status bar turn message
                    if self.current_turn == color:
                        self.status_var.set(f"Status: Your Turn ({color.capitalize()})")
                    else:
                        self.status_var.set(f"Status: Opponent's Turn ({'Black' if color == 'white' else 'White'})")
                        # Clear visual overlay on opponent's turn
                        if self.overlay:
                            self.root.after(0, self.overlay.clear)
                        # Invalidate the cache so the overlay is recomputed & redrawn the
                        # next time it's our turn, even if the position FEN is unchanged
                        # (e.g. after a transient mis-detection cleared the overlay).
                        last_calculated_fen = ""
                            
                # Think and overlay moves ONLY on player's active turn when the position has changed
                if self.current_turn == color:
                    book_moves = self.get_book_moves()
                    if book_moves:
                        full_fen = self.game_board.fen()
                        if full_fen != last_calculated_fen:
                            last_calculated_fen = full_fen
                            best_move = book_moves[0]
                            self.log("Book Moves: " + " | ".join(f"Top {idx+1}: {move_str}" for idx, move_str in enumerate(book_moves)))
                            
                            # Format book moves for the updated overlay
                            moves_data = []
                            for idx, move_str in enumerate(book_moves):
                                moves_data.append({
                                    "move": move_str,
                                    "type": "Book",
                                    "color": "#d5a478",
                                    "score": ""
                                })
                            self.root.after(0, lambda md=moves_data, fl=is_flipped: self.overlay.draw_moves(md, fl) if self.overlay else None)
                            
                            # Trigger Auto-Play
                            if self.autoplay_var.get() and full_fen != self.last_clicked_fen:
                                self.last_clicked_fen = full_fen
                                def click_worker(mv=best_move, fl=is_flipped):
                                    time.sleep(random.uniform(0.15, 0.35))
                                    self.play_move_mouse(mv, fl)
                                threading.Thread(target=click_worker, daemon=True).start()
                    else:
                        if self.engine and not self.is_thinking:
                            # Reconstruct the full FEN from our validated tracking board
                            full_fen = self.game_board.fen()
                            if full_fen != last_calculated_fen:
                                self.is_thinking = True
                                last_calculated_fen = full_fen
                                
                                def think_worker(fen_to_solve):
                                    try:
                                        b = chess.Board(fen_to_solve)
                                        if b.is_valid():
                                            # Determine analysis limit (depth or time)
                                            if self.use_time_limit_var.get():
                                                try:
                                                    t = max(0.1, float(self.time_limit_var.get()))
                                                except Exception:
                                                    t = 1.0
                                                engine_limit = chess.engine.Limit(time=t)
                                            else:
                                                engine_limit = chess.engine.Limit(depth=self.depth_var.get())

                                            analysis = self.engine.analyse(b, engine_limit, multipv=5)
                                            analysis = sorted(analysis, key=lambda x: x.get("multipv", 1))

                                            # Build one aligned list of candidate moves with their
                                            # Stockfish scores (relative = from the side-to-move's view).
                                            entries = []
                                            for entry in analysis:
                                                pv = entry.get("pv")
                                                score_obj = entry.get("score")
                                                if not pv or score_obj is None:
                                                    continue
                                                entries.append({
                                                    "move": pv[0],
                                                    "score_obj": score_obj,
                                                    "cp": score_obj.relative.score(mate_score=10000),
                                                })

                                            if not entries:
                                                self.log("Engine returned no candidate moves.")
                                                return

                                            best_score = entries[0]["cp"]
                                            second_best_score = entries[1]["cp"] if len(entries) > 1 else None

                                            def build_item(e):
                                                m_type, m_color = self.classify_move(
                                                    b, e["move"], e["cp"], best_score, second_best_score, [])
                                                return {
                                                    "move": e["move"].uci(),
                                                    "type": m_type,
                                                    "color": m_color,
                                                    "score": self._format_eval(e["score_obj"]),
                                                }

                                            moves_data = [build_item(e) for e in entries]

                                            # Maia hybrid: let the human engine pick which move is
                                            # primary (highlighted + auto-played). Stockfish still
                                            # supplies every eval score and classification.
                                            if self.maia_enabled_var.get() and self.maia_engine:
                                                maia_move = self.get_maia_move(b)
                                                if maia_move is not None:
                                                    maia_uci = maia_move.uci()
                                                    idx = next((i for i, m in enumerate(moves_data)
                                                                if m["move"] == maia_uci), None)
                                                    if idx is not None:
                                                        # Already among Stockfish's top lines: promote it.
                                                        moves_data.insert(0, moves_data.pop(idx))
                                                    else:
                                                        # Outside the top lines (a human-only choice):
                                                        # score it with Stockfish, then make it primary.
                                                        try:
                                                            # Quick, time-bounded eval of just this
                                                            # one move (for its score label). The time
                                                            # ceiling guarantees python-chess applies a
                                                            # timeout so it can never hang the loop.
                                                            info = self.engine.analyse(
                                                                b, chess.engine.Limit(depth=12, time=3.0),
                                                                root_moves=[maia_move])
                                                            if isinstance(info, list):
                                                                info = info[0]
                                                            m_score_obj = info.get("score")
                                                            m_cp = (m_score_obj.relative.score(mate_score=10000)
                                                                    if m_score_obj else best_score)
                                                            m_type, m_color = self.classify_move(
                                                                b, maia_move, m_cp, best_score,
                                                                second_best_score, [])
                                                            moves_data.insert(0, {
                                                                "move": maia_uci,
                                                                "type": m_type,
                                                                "color": m_color,
                                                                "score": self._format_eval(m_score_obj) if m_score_obj else "",
                                                            })
                                                        except Exception as me:
                                                            self.log(f"Maia move eval error: {me}")
                                                    self.log(f"Maia (human) move: {maia_uci}")

                                            log_msgs = [f"{m['type']}: {m['move']} ({m['score']})"
                                                        for m in moves_data]
                                            if log_msgs:
                                                self.log(" | ".join(log_msgs))

                                            # Apply per-label display limits
                                            label_counts = {}
                                            filtered_moves = []
                                            for m in moves_data:
                                                lbl = m["type"]
                                                limit = self._get_label_limit(lbl)
                                                cnt = label_counts.get(lbl, 0)
                                                if limit == 0 or cnt < limit:
                                                    filtered_moves.append(m)
                                                    label_counts[lbl] = cnt + 1
                                            moves_data = filtered_moves

                                            # Update UI overlay with the top classified moves
                                            self.root.after(0, lambda md=moves_data, fl=is_flipped: self.overlay.draw_moves(md, fl) if self.overlay else None)
                                            
                                            # Trigger Auto-Play
                                            if self.autoplay_var.get() and fen_to_solve != self.last_clicked_fen and moves_data:
                                                self.last_clicked_fen = fen_to_solve
                                                best_move = moves_data[0]["move"]
                                                def click_worker(mv=best_move, fl=is_flipped):
                                                    time.sleep(random.uniform(0.15, 0.35))
                                                    self.play_move_mouse(mv, fl)
                                                threading.Thread(target=click_worker, daemon=True).start()
                                    except Exception as e:
                                        self.log(f"Engine Error: {e}")
                                    finally:
                                        self.is_thinking = False
                                        
                                threading.Thread(target=think_worker, args=(full_fen,), daemon=True).start()
                            
            except Exception as e:
                self.log(f"Loop Error: {e}")
                
            time.sleep(0.1)

    def play_move_mouse(self, move_uci, flipped):
        self.is_moving_mouse = True
        try:
            x, y, w, h = self.board_bbox
            sq_size = self.sq_size
            
            # Calculate coordinates
            s_file = ord(move_uci[0]) - ord('a')
            s_rank = int(move_uci[1]) - 1
            e_file = ord(move_uci[2]) - ord('a')
            e_rank = int(move_uci[3]) - 1
            
            if not flipped:
                s_col = s_file
                s_row = 7 - s_rank
                e_col = e_file
                e_row = 7 - e_rank
            else:
                s_col = 7 - s_file
                s_row = s_rank
                e_col = 7 - e_file
                e_row = e_rank
                
            # Get start/end coordinates of square centers
            start_x = int(x + s_col * sq_size + sq_size / 2)
            start_y = int(y + s_row * sq_size + sq_size / 2)
            dest_x = int(x + e_col * sq_size + sq_size / 2)
            dest_y = int(y + e_row * sq_size + sq_size / 2)
            
            # Add random human offset (within 15% of square center)
            offset_limit = max(2, int(sq_size * 0.15))
            start_x += random.randint(-offset_limit, offset_limit)
            start_y += random.randint(-offset_limit, offset_limit)
            dest_x += random.randint(-offset_limit, offset_limit)
            dest_y += random.randint(-offset_limit, offset_limit)
            
            # Get current mouse position to start path from
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                
            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            curr_x, curr_y = pt.x, pt.y
            
            # 1. Move to start square (hover)
            path1 = self.generate_windmouse_path(curr_x, curr_y, start_x, start_y)
            for px, py in path1:
                ctypes.windll.user32.SetCursorPos(px, py)
                time.sleep(random.uniform(0.003, 0.006))
                
            time.sleep(random.uniform(0.1, 0.18)) # Pause before clicking
            
            # 2. Click start (press mouse down)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0) # LEFTDOWN
            time.sleep(random.uniform(0.05, 0.12))
            
            # 3. Drag to destination square (slightly slower, more deliberate)
            path2 = self.generate_windmouse_path(start_x, start_y, dest_x, dest_y)
            for px, py in path2:
                ctypes.windll.user32.SetCursorPos(px, py)
                time.sleep(random.uniform(0.007, 0.014))
                
            time.sleep(random.uniform(0.08, 0.15)) # Pause before releasing
            
            # 4. Release mouse button (mouse up)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0) # LEFTUP
            time.sleep(random.uniform(0.1, 0.2))
            
            # Handle pawn promotion (uci e.g. e7e8q)
            if len(move_uci) == 5:
                # Sleep to simulate choosing the piece
                time.sleep(random.uniform(0.3, 0.5))
                # Click the destination square again to select Queen
                ctypes.windll.user32.SetCursorPos(dest_x, dest_y)
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0) # DOWN
                time.sleep(random.uniform(0.05, 0.1))
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0) # UP
                time.sleep(random.uniform(0.1, 0.2))
        except Exception as me:
            self.log(f"Mouse Simulation Error: {me}")
        finally:
            self.is_moving_mouse = False

    def generate_windmouse_path(self, start_x, start_y, dest_x, dest_y):
        # Calculate distance
        dist = ((dest_x - start_x) ** 2 + (dest_y - start_y) ** 2) ** 0.5
        if dist < 5:
            return [(dest_x, dest_y)]
            
        # Determine number of steps based on distance (15 to 30 steps)
        steps = int(max(15, min(30, dist / 15)))
        
        # Create control points P1 and P2 for a cubic Bezier curve
        # Offset them perpendicular to the path by up to 8% of the distance
        dx = dest_x - start_x
        dy = dest_y - start_y
        
        px = -dy
        py = dx
        p_len = (px**2 + py**2)**0.5
        if p_len > 0:
            px /= p_len
            py /= p_len
            
        curve_mag = random.uniform(-0.08, 0.08) * dist
        
        p1_x = start_x + dx * 0.25 + px * curve_mag
        p1_y = start_y + dy * 0.25 + py * curve_mag
        
        p2_x = start_x + dx * 0.75 + px * curve_mag
        p2_y = start_y + dy * 0.75 + py * curve_mag
        
        points = []
        for i in range(1, steps + 1):
            progress = i / steps
            # Smoothstep easing curve
            t = progress * progress * (3 - 2 * progress)
            
            # Bezier formula
            x = (1-t)**3 * start_x + 3*(1-t)**2 * t * p1_x + 3*(1-t) * t**2 * p2_x + t**3 * dest_x
            y = (1-t)**3 * start_y + 3*(1-t)**2 * t * p1_y + 3*(1-t) * t**2 * p2_y + t**3 * dest_y
            
            points.append((int(round(x)), int(round(y))))
            
        return points

    def stop_bot(self):
        self.is_running = False
        self.status_var.set("Status: Stopped")
        self.log("Bot stopped.")
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        self.btn_white.config(state=tk.NORMAL)
        self.btn_black.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def on_closing(self):
        self.is_running = False
        if self.overlay:
            self.overlay.close()
            self.overlay = None
        if self.engine:
            self.engine.quit()
        if self.maia_engine:
            try:
                self.maia_engine.quit()
            except Exception:
                pass
            self.maia_engine = None
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use('clam')
    app = ChessBotPro(root)
    
    def check_hotkeys():
        try:
            if keyboard.is_pressed('alt+w') and not app.is_running:
                app.root.after(0, lambda: app.start_bot("white"))
            elif keyboard.is_pressed('alt+b') and not app.is_running:
                app.root.after(0, lambda: app.start_bot("black"))
            elif keyboard.is_pressed('alt+x') and app.is_running:
                app.root.after(0, app.stop_bot)
        except Exception:
            pass
        app.root.after(100, check_hotkeys)
    app.root.after(100, check_hotkeys)
    
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
