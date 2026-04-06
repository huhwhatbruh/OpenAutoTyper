#!/usr/bin/env python3
"""
OpenAutoTyper v1.0.0 — Human-realistic keyboard simulation.

Cross-platform (Linux / Windows). Uses customtkinter for a modern UI
and a sophisticated typing engine that mimics real human keystroke patterns
to evade auto-typing detection.

Dependencies:
    pip install customtkinter pyautogui pyperclip
"""

from __future__ import annotations

import customtkinter as ctk
import tkinter as tk
import webbrowser
import time
import random
import math
import multiprocessing
import sys
import os
import platform

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Cross-platform font detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_IS_WINDOWS = platform.system() == "Windows"
_IS_LINUX = platform.system() == "Linux"
_IS_MAC = platform.system() == "Darwin"

if _IS_WINDOWS:
    FONT_FAMILY = "Segoe UI"
    MONO_FAMILY = "Consolas"
elif _IS_MAC:
    FONT_FAMILY = "SF Pro Display"
    MONO_FAMILY = "SF Mono"
else:  # Linux
    FONT_FAMILY = "sans-serif"
    MONO_FAMILY = "monospace"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Theme / Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

VERSION = "1.0.0"
APP_TITLE = "OpenAutoTyper"

# Human-typing tunables
WPM_JITTER       = 0.20    # ±20 % speed wander
BURST_SPEEDUP    = 1.30    # common short words are typed faster

# Common short words that people type as bursts (faster)
COMMON_WORDS = frozenset({
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
    'had', 'her', 'was', 'one', 'our', 'out', 'has', 'his', 'how',
    'its', 'may', 'new', 'now', 'old', 'see', 'way', 'who', 'did',
    'get', 'let', 'say', 'she', 'too', 'use', 'is', 'it', 'to', 'in',
    'of', 'a', 'i', 'on', 'at', 'if', 'do', 'an', 'no', 'so', 'we',
    'my', 'up', 'or', 'by', 'be', 'he', 'me', 'as', 'go',
})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Human-like Typing Engine  (runs in a subprocess)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _gaussian_delay(mean: float, std: float) -> float:
    """Return a Gaussian-distributed delay, clamped to a sane range."""
    d = random.gauss(mean, std)
    return max(mean * 0.25, min(d, mean * 3.5))


def _inter_key_delay(base_interval: float) -> float:
    """
    Generate a single inter-keystroke delay with human-like variance.
    Uses a Gaussian distribution with occasional micro-hesitations.
    """
    # Occasional micro-hesitation (~3% of keystrokes)
    if random.random() < 0.033:
        return _gaussian_delay(base_interval * 2.5, base_interval * 0.6)
    return _gaussian_delay(base_interval, base_interval * 0.22)


def _word_pause(pause_chance: float, max_pause: float) -> float:
    """
    Decide whether to pause after a word and for how long.
    Models the human tendency to pause mid-sentence while thinking.
    """
    if random.random() * 100 >= pause_chance:
        return 0.0
    # Use a log-normal distribution so most pauses are short
    mu = math.log(max(max_pause * 0.35, 0.01))
    sigma = 0.55
    pause = min(random.lognormvariate(mu, sigma), max_pause)
    return max(0.12, pause)


def _type_single_char(pag, ch: str) -> None:
    """
    Type a single character using the most reliable cross-platform method.
    - For newline / tab: use press() with the key name
    - For carriage return: skip (handled by newline)
    - For ASCII printable: use press() with the character
    - For non-ASCII (unicode): use clipboard paste
    """
    if ch == '\n':
        pag.press('enter')
    elif ch == '\t':
        pag.press('tab')
    elif ch == '\r':
        return  # skip bare CR; \r\n already handled via \n
    elif 32 <= ord(ch) <= 126:
        # Standard ASCII printable — use press() which is more reliable
        # than write() for single characters
        pag.press(ch)
    else:
        # Unicode character — clipboard paste it
        try:
            import pyperclip
            pyperclip.copy(ch)
            # Ctrl+V on Windows/Linux, Cmd+V on Mac
            if platform.system() == "Darwin":
                pag.hotkey('command', 'v')
            else:
                pag.hotkey('ctrl', 'v')
        except Exception:
            # Fallback to write() even though it may fail on non-ASCII
            try:
                pag.write(ch, interval=0)
            except Exception:
                pass


def typing_process(
    delay: float,
    interval: float,
    data: str,
    realistic_enabled: bool,
    pause_chance: float,
    max_pause: float,
) -> None:
    """
    Main typing entry-point — executed in a *subprocess*.

    Parameters
    ----------
    delay             : seconds to wait before typing starts
    interval          : base seconds between each keystroke
    data              : the text to type
    realistic_enabled : whether to add word-level pauses
    pause_chance      : 0-100 probability of pausing after each word
    max_pause         : maximum pause duration in seconds
    """
    delay = float(delay)
    interval = float(interval)
    pause_chance = float(pause_chance)
    max_pause = float(max_pause)

    time.sleep(delay)

    import pyautogui
    pyautogui.FAILSAFE = True  # move mouse to top-left corner to emergency abort

    # Normalize line endings: \r\n -> \n, lone \r -> \n
    data = data.replace('\r\n', '\n').replace('\r', '\n')

    # Apply initial WPM jitter
    speed_factor = 1.0 + random.uniform(-WPM_JITTER, WPM_JITTER)
    effective_interval = interval * speed_factor

    i = 0
    length = len(data)

    while i < length:
        ch = data[i]

        # ── Whitespace: type it and move on ──
        if ch in (' ', '\t', '\n'):
            time.sleep(_inter_key_delay(effective_interval))
            _type_single_char(pyautogui, ch)
            i += 1
            continue

        # ── Collect the full word ──
        word_start = i
        while i < length and data[i] not in (' ', '\t', '\n', '\r'):
            i += 1
        word = data[word_start:i]

        # Common short words are typed as fast bursts
        word_interval = effective_interval
        if word.lower().strip(".,;:!?\"'()-") in COMMON_WORDS:
            word_interval = effective_interval / BURST_SPEEDUP

        # Type each character of the word
        for c in word:
            time.sleep(_inter_key_delay(word_interval))
            _type_single_char(pyautogui, c)

        # After a full word: maybe pause (if realistic mode is on)
        if realistic_enabled and pause_chance > 0 and max_pause > 0:
            p = _word_pause(pause_chance, max_pause)
            if p > 0:
                time.sleep(p)

        # Subtle speed drift every ~10% of words
        if random.random() < 0.10:
            speed_factor = 1.0 + random.uniform(-WPM_JITTER, WPM_JITTER)
            effective_interval = interval * speed_factor


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Custom Toast Notification  (replaces all tkinter messageboxes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Toast(ctk.CTkToplevel):
    """
    A small, auto-dismissing notification that appears at the top-right.
    Types: 'info', 'success', 'warning', 'error'.
    """

    COLORS = {
        "info":    ("#3b82f6", "ℹ"),
        "success": ("#22c55e", "✓"),
        "warning": ("#f59e0b", "⚠"),
        "error":   ("#ef4444", "✕"),
    }

    # Track active toasts for stacking — instance list, not shared mutably
    _active: list["Toast"] = []

    def __init__(self, parent: ctk.CTk, message: str,
                 kind: str = "info", duration: int = 3000):
        super().__init__(parent)

        color, icon = self.COLORS.get(kind, self.COLORS["info"])

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.95)
        except tk.TclError:
            pass  # some Linux WMs don't support alpha

        self.configure(fg_color=("#1e1e2e", "#1e1e2e"))

        # ── Layout ────────────────────────────────────────────
        frame = ctk.CTkFrame(
            self, fg_color=("#1e1e2e", "#1e1e2e"),
            border_color=color, border_width=2, corner_radius=10,
        )
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            frame, text=icon, font=(FONT_FAMILY, 18, "bold"),
            text_color=color, width=30,
        ).pack(side="left", padx=(14, 6), pady=12)

        ctk.CTkLabel(
            frame, text=message, font=(FONT_FAMILY, 12),
            text_color="#cdd6f4", wraplength=280, justify="left",
        ).pack(side="left", padx=(0, 18), pady=12, fill="x", expand=True)

        # ── Position (top-right of current monitor) ───────────
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 340)
        h = self.winfo_reqheight()

        # Multi-monitor fix: Detect individual monitor width from aggregate desktop.
        total_w = self.winfo_screenwidth()
        center_x = parent.winfo_rootx() + (parent.winfo_width() // 2)
        
        # Heuristic: Identify monitor width based on common resolutions.
        monitor_w = total_w
        for res in [1920, 2560, 3840, 1440, 1680, 1280]:
            if total_w % res == 0 and res < total_w:
                monitor_w = res
                break
        
        # Calculate the right-hand corner of the monitor containing the app.
        monitor_right_edge = ((center_x // monitor_w) + 1) * monitor_w
        x = monitor_right_edge - w - 28
        
        # Failsafe: Ensure it doesn't go off the desktop left boundary.
        if x < 10:
            x = 10

        base_y = 28
        # Stack below any existing toasts
        still_alive = []
        for t in Toast._active:
            try:
                if t.winfo_exists():
                    # Only stack toasts appearing on the same monitor
                    if abs(t.winfo_x() - x) < 500:
                        base_y += t.winfo_height() + 10
                        still_alive.append(t)
            except Exception:
                pass
        Toast._active = still_alive

        self.geometry(f"{w}x{h}+{x}+{base_y}")
        Toast._active.append(self)

        # Auto-dismiss
        self._after_id = self.after(duration, self._dismiss)

    def _dismiss(self) -> None:
        try:
            Toast._active.remove(self)
        except ValueError:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def show_toast(parent: ctk.CTk, message: str,
               kind: str = "info", duration: int = 3000) -> None:
    """Show a non-blocking toast notification."""
    try:
        Toast(parent, message, kind, duration)
    except Exception:
        pass  # never crash the app because of a notification


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Styled Confirm Dialog  (replaces messagebox.askyesno)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ConfirmDialog(ctk.CTkToplevel):
    """Modal yes / no dialog styled to match the app."""

    def __init__(self, parent: ctk.CTk, title: str, message: str):
        super().__init__(parent)
        self.result: bool = False
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=("#1e1e2e", "#1e1e2e"))
        self.attributes("-topmost", True)

        ctk.CTkLabel(
            self, text=message, font=(FONT_FAMILY, 13),
            text_color="#cdd6f4", wraplength=320, justify="center",
        ).pack(padx=30, pady=(28, 18))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 22))

        ctk.CTkButton(
            btn_frame, text="Yes", width=100, height=34,
            fg_color="#22c55e", hover_color="#16a34a",
            text_color="#000", font=(FONT_FAMILY, 12, "bold"),
            corner_radius=8, command=self._yes,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="No", width=100, height=34,
            fg_color="#45475a", hover_color="#585b70",
            text_color="#cdd6f4", font=(FONT_FAMILY, 12, "bold"),
            corner_radius=8, command=self._no,
        ).pack(side="left", padx=8)

        # Center on parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

        self.protocol("WM_DELETE_WINDOW", self._no)
        self.grab_set()
        self.wait_window()

    def _yes(self) -> None:
        self.result = True
        self.grab_release()
        self.destroy()

    def _no(self) -> None:
        self.result = False
        self.grab_release()
        self.destroy()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Application
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AutoTyperApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.process: "multiprocessing.Process | None" = None
        self._typing_started = False

        self._setup_window()
        self._build_ui()

    # ── Window ────────────────────────────────────────────────
    def _setup_window(self) -> None:
        self.title(APP_TITLE)
        self.geometry("720x680")
        self.minsize(620, 580)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Build UI ──────────────────────────────────────────────
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        # Row weights: 0=header, 1=card, 2=toggle, 3=textbox(expand), 4=status, 5=buttons, 6=footer
        for r in (0, 1, 2, 4, 5, 6):
            self.grid_rowconfigure(r, weight=0)
        self.grid_rowconfigure(3, weight=1)

        # ── Header ────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=28, pady=(22, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="⌨", font=(FONT_FAMILY, 34),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 14))

        ctk.CTkLabel(
            header, text=APP_TITLE,
            font=(FONT_FAMILY, 26, "bold"), anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            header, text="Paste your text, configure timing, and let it type for you.",
            font=(FONT_FAMILY, 12), text_color="#a6adc8", anchor="w",
        ).grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(
            header, text=f"v{VERSION}",
            font=(FONT_FAMILY, 11), text_color="#585b70",
        ).grid(row=0, column=2, sticky="ne", padx=(8, 0))

        # ── Settings Card ────────────────────────────────────
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=1, column=0, padx=28, pady=(6, 4), sticky="ew")
        card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        param_specs = [
            ("delay",        "Initial Delay (s)",     "Wait before typing starts",        "5"),
            ("interval",     "Key Interval (s)",      "Base time between keystrokes",     "0.06"),
            ("pause_chance", "Pause Chance (%)",      "Chance of pausing after a word",   "18"),
            ("max_pause",    "Max Pause (s)",         "Longest possible word-pause",      "2.5"),
        ]
        self._entries: dict[str, ctk.CTkEntry] = {}

        for col, (key, label, tip, default) in enumerate(param_specs):
            ctk.CTkLabel(
                card, text=label, font=(FONT_FAMILY, 11, "bold"),
                text_color="#cdd6f4",
            ).grid(row=0, column=col, padx=14, pady=(14, 0), sticky="w")

            ctk.CTkLabel(
                card, text=tip, font=(FONT_FAMILY, 9),
                text_color="#6c7086",
            ).grid(row=1, column=col, padx=14, pady=(0, 3), sticky="w")

            ent = ctk.CTkEntry(
                card, height=36, corner_radius=8,
                font=(MONO_FAMILY, 12), justify="center",
                border_color="#45475a", fg_color="#313150",
            )
            ent.insert(0, default)
            ent.grid(row=2, column=col, padx=14, pady=(0, 16), sticky="ew")
            self._entries[key] = ent

        # ── Realistic toggle ─────────────────────────────────
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.grid(row=2, column=0, padx=28, pady=(2, 2), sticky="ew")
        toggle_frame.grid_columnconfigure(1, weight=1)

        self.realistic_var = ctk.BooleanVar(value=True)
        self.realistic_switch = ctk.CTkSwitch(
            toggle_frame, text="Realistic Mode",
            variable=self.realistic_var,
            font=(FONT_FAMILY, 12, "bold"),
            onvalue=True, offvalue=False,
            command=self._toggle_realistic,
        )
        self.realistic_switch.grid(row=0, column=0, padx=(0, 14))

        ctk.CTkLabel(
            toggle_frame,
            text="Human-like speed variation, micro-hesitations, burst-typing common words, and random pauses after full words.",
            font=(FONT_FAMILY, 10), text_color="#6c7086",
            wraplength=460, justify="left", anchor="w",
        ).grid(row=0, column=1, sticky="w")

        # ── Text Area Container ──────────────────────────────
        text_container = ctk.CTkFrame(self, corner_radius=12)
        text_container.grid(row=3, column=0, padx=28, pady=(6, 6), sticky="nsew")
        text_container.grid_columnconfigure(0, weight=1)
        text_container.grid_rowconfigure(1, weight=1)

        text_header = ctk.CTkFrame(text_container, fg_color="transparent")
        text_header.grid(row=0, column=0, padx=14, pady=(10, 2), sticky="ew")
        text_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            text_header, text="Text to Type",
            font=(FONT_FAMILY, 13, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.count_label = ctk.CTkLabel(
            text_header, text="0 chars  ·  0 words",
            font=(FONT_FAMILY, 10), text_color="#6c7086", anchor="e",
        )
        self.count_label.grid(row=0, column=1, sticky="e")

        self.textbox = ctk.CTkTextbox(
            text_container, corner_radius=8,
            font=(MONO_FAMILY, 12), wrap="word",
            fg_color="#313150", border_color="#45475a",
            border_width=1,
            scrollbar_button_color="#585b70",
            scrollbar_button_hover_color="#89b4fa",
        )
        self.textbox.grid(row=1, column=0, padx=10, pady=(2, 12), sticky="nsew")

        # Bind events for live character count
        self.textbox.bind("<KeyRelease>", self._update_counts)
        # Handle paste
        self.textbox.bind("<<Paste>>", lambda e: self.after(50, self._update_counts))
        # Ctrl+A select all — bind on the underlying tk.Text widget
        self.textbox.bind("<Control-a>", self._select_all)
        self.textbox.bind("<Control-A>", self._select_all)

        # ── Status Bar ────────────────────────────────────────
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=4, column=0, padx=28, pady=(0, 2), sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_indicator = ctk.CTkLabel(
            status_frame, text="● Idle", font=(FONT_FAMILY, 11, "bold"),
            text_color="#6c7086", anchor="w",
        )
        self.status_indicator.grid(row=0, column=0, sticky="w")

        self.eta_label = ctk.CTkLabel(
            status_frame, text="",
            font=(FONT_FAMILY, 10), text_color="#6c7086", anchor="e",
        )
        self.eta_label.grid(row=0, column=1, sticky="e")

        # ── Action Buttons ────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=28, pady=(4, 6), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.start_btn = ctk.CTkButton(
            btn_frame, text="▶  Start Typing", height=44,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=10,
            fg_color="#22c55e", hover_color="#16a34a",
            text_color="#000", command=self._start,
        )
        self.start_btn.grid(row=0, column=0, padx=6, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="■  Stop", height=44,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=10,
            fg_color="#ef4444", hover_color="#dc2626",
            text_color="#fff", command=self._stop,
            state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, padx=6, sticky="ew")

        ctk.CTkButton(
            btn_frame, text="Clear", height=44,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=10,
            fg_color="#45475a", hover_color="#585b70",
            text_color="#cdd6f4", command=self._clear,
        ).grid(row=0, column=2, padx=6, sticky="ew")

        ctk.CTkButton(
            btn_frame, text="About", height=44,
            font=(FONT_FAMILY, 13, "bold"), corner_radius=10,
            fg_color="#45475a", hover_color="#585b70",
            text_color="#cdd6f4", command=self._about,
        ).grid(row=0, column=3, padx=6, sticky="ew")

        # ── Footer ────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Tip: Move your mouse to any screen corner to emergency-stop typing (PyAutoGUI failsafe)",
            font=(FONT_FAMILY, 10), text_color="#585b70",
        ).grid(row=6, column=0, pady=(2, 14))

        # ── Start polling ─────────────────────────────────────
        self._poll_process()

    # ── Toggle realistic mode ─────────────────────────────────
    def _toggle_realistic(self) -> None:
        enabled = self.realistic_var.get()
        state = "normal" if enabled else "disabled"
        self._entries["pause_chance"].configure(state=state)
        self._entries["max_pause"].configure(state=state)

    # ── Live character / word count ───────────────────────────
    def _update_counts(self, _event: "tk.Event | None" = None) -> None:
        text = self.textbox.get("1.0", "end-1c")
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.count_label.configure(text=f"{chars:,} chars  ·  {words:,} words")

        # Update ETA estimate
        try:
            interval = float(self._entries["interval"].get())
            eta_secs = chars * interval
            if eta_secs < 60:
                self.eta_label.configure(text=f"~{eta_secs:.0f}s to type")
            else:
                mins = int(eta_secs // 60)
                secs = int(eta_secs % 60)
                self.eta_label.configure(text=f"~{mins}m {secs}s to type")
        except (ValueError, KeyError):
            self.eta_label.configure(text="")

    # ── Select all ────────────────────────────────────────────
    def _select_all(self, event: "tk.Event") -> str:
        # CTkTextbox wraps a tk.Text — we need to operate on it
        self.textbox.tag_add("sel", "1.0", "end-1c")
        return "break"

    # ── Validate inputs ───────────────────────────────────────
    def _validate(self) -> "dict[str, float] | None":
        """Parse and validate all entry fields. Returns dict or None on error."""
        vals: dict[str, float] = {}
        for key, entry in self._entries.items():
            raw = entry.get().strip()
            if not raw:
                show_toast(self, f"'{key}' field cannot be empty.", "error")
                entry.focus_set()
                return None
            try:
                vals[key] = float(raw)
            except ValueError:
                show_toast(self, f"'{key}' must be a valid number.", "error")
                entry.focus_set()
                return None

        # Range checks
        if vals["delay"] < 0:
            show_toast(self, "Initial delay cannot be negative.", "error")
            return None
        if vals["interval"] <= 0:
            show_toast(self, "Key interval must be greater than 0.", "error")
            return None
        if not (0 <= vals["pause_chance"] <= 100):
            show_toast(self, "Pause chance must be between 0 and 100.", "error")
            return None
        if vals["max_pause"] < 0:
            show_toast(self, "Max pause cannot be negative.", "error")
            return None

        return vals

    # ── Start typing ──────────────────────────────────────────
    def _start(self) -> None:
        if self.process is not None and self.process.is_alive():
            show_toast(self, "Typing is already in progress.", "warning")
            return

        vals = self._validate()
        if vals is None:
            return

        data = self.textbox.get("1.0", "end-1c")
        if not data.strip():
            show_toast(self, "Paste some text into the box first.", "warning")
            return

        self.process = multiprocessing.Process(
            target=typing_process,
            args=(
                vals["delay"],
                vals["interval"],
                data,
                self.realistic_var.get(),
                vals["pause_chance"],
                vals["max_pause"],
            ),
            daemon=True,
        )
        self.process.start()
        self._typing_started = True

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_indicator.configure(text="● Waiting…", text_color="#f59e0b")

        delay_s = int(vals["delay"])
        show_toast(
            self,
            f"Typing begins in {delay_s} second{'s' if delay_s != 1 else ''}. Click the target window now.",
            "success",
            duration=max(min(delay_s * 1000, 6000), 2000),
        )

    # ── Stop typing ───────────────────────────────────────────
    def _stop(self) -> None:
        if self.process is not None and self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=3)
            if self.process.is_alive():
                self.process.kill()  # force kill if terminate didn't work
                self.process.join(timeout=1)
            self.process = None
            self._typing_started = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_indicator.configure(text="● Stopped", text_color="#ef4444")
            show_toast(self, "Typing stopped.", "info")
        else:
            show_toast(self, "Nothing is currently typing.", "info")

    # ── Clear text ────────────────────────────────────────────
    def _clear(self) -> None:
        text = self.textbox.get("1.0", "end-1c")
        if text.strip():
            dlg = ConfirmDialog(self, "Clear Text", "Clear all text from the editor?")
            if not dlg.result:
                return
        self.textbox.delete("1.0", "end")
        self._update_counts()
        show_toast(self, "Text cleared.", "info", 1500)

    # ── Poll subprocess state ─────────────────────────────────
    def _poll_process(self) -> None:
        if self.process is not None:
            if self.process.is_alive():
                if self._typing_started:
                    self.status_indicator.configure(
                        text="● Typing…", text_color="#22c55e",
                    )
            else:
                # Process finished on its own
                exit_code = self.process.exitcode
                self.process = None
                self._typing_started = False
                self.start_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")

                if exit_code == 0:
                    self.status_indicator.configure(text="● Done", text_color="#3b82f6")
                    show_toast(self, "Typing complete!", "success", 3000)
                else:
                    self.status_indicator.configure(text="● Error", text_color="#ef4444")
                    show_toast(
                        self,
                        f"Typing process exited with code {exit_code}. "
                        "Check if the target window was available.",
                        "error", 5000,
                    )

        self.after(400, self._poll_process)

    # ── About window ──────────────────────────────────────────
    def _about(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("About")
        win.geometry("420x340")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.after(100, win.grab_set)  # slight delay avoids Linux grab race

        ctk.CTkLabel(
            win, text="⌨", font=(FONT_FAMILY, 38),
        ).pack(pady=(22, 4))

        ctk.CTkLabel(
            win, text=f"Auto Typer  v{VERSION}",
            font=(FONT_FAMILY, 22, "bold"),
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            win, text="Human-realistic auto-typing tool",
            font=(FONT_FAMILY, 11), text_color="#6c7086",
        ).pack()

        ctk.CTkLabel(
            win, text="Created by huhwhatbruh",
            font=(FONT_FAMILY, 11), text_color="#a6adc8",
        ).pack(pady=(10, 6))

        links_frame = ctk.CTkFrame(win, fg_color="transparent")
        links_frame.pack(pady=6)

        ctk.CTkButton(
            links_frame, text="GitHub ↗", width=140,
            font=(FONT_FAMILY, 11), fg_color="transparent",
            hover_color="#313150", text_color="#89b4fa",
            command=lambda: webbrowser.open_new("https://github.com/huhwhatbruh/OpenAutoTyper"),
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            win, text="Close", width=120, height=34,
            fg_color="#45475a", hover_color="#585b70",
            corner_radius=8, command=win.destroy,
        ).pack(pady=(4, 18))

    # ── Window close ──────────────────────────────────────────
    def _on_close(self) -> None:
        if self.process is not None and self.process.is_alive():
            dlg = ConfirmDialog(
                self, "Quit",
                "Typing is still in progress. Quit anyway?",
            )
            if not dlg.result:
                return
            self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
        self.destroy()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AutoTyperApp()
    app.mainloop()
