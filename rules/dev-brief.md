# Development Brief

- Product: Windows PyQt desktop tool for window move, resize, and profiles.
- Operator mode: run `run_gui.py` for development or `dist/WindowResizer.exe` after a build.
- Current release focus: reliable profile application and visible, consistent themes.
- UX principle: movement lock is opt-in and separate from mouse constraint.
- UX principle: text, controls, alternate table rows, and confirmation dialogs must remain readable in every theme.
- UX principle: a system-theme preference follows the detected Windows theme, and an unmatched manual action reports its result in the status bar.
- Reliability principle: profile saves are atomic and recover from the last backup; a cursor release must remove the Win32 clip rectangle across all monitors.
- Build principle: a clean checkout builds without generated assets such as `dist/icon.ico`.
- Non-goals: public API, CLI contract, plugin system, and unverified automation features.
