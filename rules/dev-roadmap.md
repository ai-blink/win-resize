# Implementation Roadmap

| Milestone | Status | Evidence | Updated | Next action |
|---|---|---|---|---|
| Profile movement options | Done | Focused test passed | 2026-07-31 | Regress only on a new report |
| Profile preview and automatic apply | Done | 5 focused tests and executable smoke check passed | 2026-07-31 | Manually verify with a multi-monitor launch |
| Executable path profile matching | Done | 8 focused tests and executable build passed | 2026-07-31 | Verify one path-based automatic application with a real app launch |
| Profile create and delete flow | Done | Added-profile deletion regression test passed | 2026-07-31 | Regress on future profile list changes |
| Close-to-tray lifecycle | Done | Focused close-to-tray regression test passed | 2026-07-31 | Manually confirm tray restore and explicit exit in the packaged app |
| Theme visibility baseline | Done | Focused test and executable build passed | 2026-07-31 | Check light and dark UI reports |
| Review hardening | In progress | 23 public tests passed; native cursor release passed; PyInstaller blocked only by locked existing EXE | 2026-07-31 | Close running EXE and rerun official build |
| Release smoke test | Planned | No packaged release smoke record | 2026-07-31 | Run a manual light/dark confirmation flow before release |
