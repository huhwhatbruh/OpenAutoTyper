# OpenAutoTyper v1.0.0

**OpenAutoTyper** is a highly advanced, semantic auto-typing tool designed for users who need to bypass modern auto-typer detection mechanics. Whether you're pasting data into restricted environments or simulating natural typing, this tool uses sophisticated variance algorithms to emulate authentic human behavior.

Created by **[huhwhatbruh](https://github.com/huhwhatbruh)**.

---

## What's New in v1.0.0?
- **Complete UI Overhaul**: Features a modern, dark-themed GUI built using `customtkinter`.
- **Advanced Human Emulation Engine**: Moves beyond simple static delays by incorporating Gaussian randomness, typing burst bursts, micro-hesitations, and word-level pauses.
- **Cross-Platform Compatibility**: Native support out-of-the-box for Windows and Linux, complete with dynamic cross-platform typography and Unicode character clipboard injection.
- **Live ETA & Word Counts**: Monitor exactly how long it takes to finish typing your pasted text directly from the dashboard.
- **Robust Exception Handling**: Failsafes and fallback mechanics prevent app crashes even during complex multi-thread typing sequences.

## The Human-Realistic Engine

Unlike traditional scripts that use a fixed `interval`, OpenAutoTyper simulates *you*:

*   **Gaussian Variance Delay**: Your keystrokes randomly fluctuate based on a bell-curve (Gaussian) distribution, mapping perfectly to how human hands type faster for some characters and slower for others.
*   **Word-Level Pauses ("Realistic Mode")**: Simulates a human "thinking." It groups characters by word, reading the text before typing. You can define a percentage chance that the typer will naturally "pause" between sentences and words, adjusting the max length of these pauses yourself.
*   **Burst Typing**: The typer recognizes over 50 of the most commonly typed English words ("the", "and", "because", "but"). When encountering them, it switches into "burst speed," reproducing how people memorize and rapidly type short conjunctions.
*   **WPM Drift**: Over long stretches of text, a person's typing speed "drifts." OpenAutoTyper naturally drifts its WPM baseline ±20% every handful of paragraphs. 

---

## Installation

### Requirements
- Python 3.x

### Dependencies
Install the required python packages using PIP:
```bash
pip install customtkinter pyautogui pyperclip
```

**Note for Linux users:**
If your environment does not have native clipboard CLI drivers (needed for `pyperclip`), you must install either `xclip` or `xsel`:
*   *Arch:* `sudo pacman -S xclip`
*   *Debian/Ubuntu:* `sudo apt install xclip`

## Usage

Launch the modernized graphical interface with:
```bash
python autoTyperGUI.py
```

### Parameters Guide
- **Initial Delay (sec)**: The countdown time before the app starts taking over your keyboard.
- **Keystroke Interval (sec)**: The mathematical baseline interval per character (e.g., `0.06`).
- **Pause Chance (%)**: In Realistic Mode, the % likelihood that the typing will "stop to think" after finishing a full word.
- **Max Pause (sec)**: The upper limit to how long the script will randomly pause between those words.

*Emergency Stop:* Simply whip your mouse to any of the 4 direct corners of your screen. PyAutoGUI's built-in `FAILSAFE` mechanism will instantly terminate the typing sequence.

---

## License

This project is licensed under the MIT License - open sourced for the community.
