# Implementation Roadmap

| Milestone | Status | Evidence | Updated | Next action |
|---|---|---|---|---|
| Profile movement options | Done | Focused test passed | 2026-07-31 | Regress only on a new report |
| Profile preview and automatic apply | Done | 5 focused tests and executable smoke check passed | 2026-07-31 | Manually verify with a multi-monitor launch |
| Executable path profile matching | Done | 8 focused tests and executable build passed | 2026-07-31 | Verify one path-based automatic application with a real app launch |
| Profile create and delete flow | Done | Added-profile deletion regression test passed | 2026-07-31 | Regress on future profile list changes |
| Close-to-tray lifecycle | Done | Focused close-to-tray regression test passed | 2026-07-31 | Manually confirm tray restore and explicit exit in the packaged app |
| Theme visibility baseline | Done | Focused test and executable build passed | 2026-07-31 | Check light and dark UI reports |
| Review hardening | Done | 23 public tests passed; native cursor release passed; official PyInstaller build and packaged startup smoke passed | 2026-07-31 | Regress only on a new report |
| Release smoke test | Done | Rebuilt EXE started for 10 seconds and exited cleanly; SHA-256 recorded | 2026-07-31 | Perform light/dark and tray visual QA post-release |
| Single-instance startup protection | Done | Focused regression tests, 35-test discovery, native mutex check, and official EXE rebuild passed | 2026-08-04 | Regress on a future launcher change |
| Apply All refresh sequencing | Done | Focused two-test regression, 36-test discovery, and official EXE rebuild passed | 2026-08-10 | Manually verify one-click application against a newly opened target window |
| Realtime profile application | Done | Focused toggle regression tests passed; official EXE build and package log confirmed new-window monitoring starts for one active real-time profile | 2026-08-11 | Manually verify one newly launched Blender window restores after move or resize |
| UI scale and persistence | Done | 7 dedicated tests, 47-test discovery, official EXE rebuild, and packaged startup passed | 2026-08-11 | Manually verify the slider and restored main-window geometry in the packaged application |
| Profile hotkey persistence and registration | Done | Dedicated 5-test regression, 52-test discovery, actual key-input callback, and official EXE rebuild passed | 2026-08-17 | Replace the running EXE, then manually save Ctrl+Alt+E once and verify it applies the profile |
