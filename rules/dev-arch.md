# Development Architecture

## Layers

- `src/gui/`: PyQt windows, dialogs, tables, profile editor, and theme-facing UI.
- `src/core/`: profiles and application rules.
- `src/utils/`: Windows discovery and native manipulation helpers.
- `src/gui/theme_manager.py`: the single runtime source for Qt theme palette and global dialog styling.
- `src/gui/ui_scale_manager.py`: persisted application UI scale and main-window geometry settings.
- `src/core/window_state_manager.py`: transparency animation state and timers.
- `src/core/integrated_mouse_constraint.py`: Win32 cursor clipping and release.
- `src/core/hotkey_manager.py`: Windows global shortcut registration and native `WM_HOTKEY` dispatch.

## Responsibilities

- GUI gathers user intent and renders state; it does not call Win32 APIs directly when a core or utility service owns that behavior.
- `Profile` applies stored geometry before optional position locking.
- Position lock and mouse constraint are independent profile flags.
- Theme-specific colors must come from `ThemeManager` rather than fixed dark or light literals.
- UI scale changes apply only to WindowResizer visuals; saved profile geometry and
  native target-window operations remain unscaled. The main window restores its
  saved size and position only when that geometry remains visible on a current screen.
- Profile persistence writes a temporary file, retains a backup, then atomically replaces the primary file.
- Profile shortcuts persist their enabled sets on the profile and are registered again after startup or profile changes. Their native messages are handled through Qt's native event filter.
- The build command uses `src` as its analysis path and treats a source-controlled `.ico` file as optional.

## Key Paths

| Purpose | Path |
|---|---|
| Main window | `src/gui/main_window.py` |
| Profile editor | `src/gui/profile_editor.py` |
| Profile persistence and locking | `src/core/profile_manager.py` |
| Profile hotkey registration | `src/core/hotkey_manager.py` |
| Theme palette and global Qt styles | `src/gui/theme_manager.py` |
| UI scale and main-window geometry persistence | `src/gui/ui_scale_manager.py` |
| Current UI regression test | `tests/test_profile_editor_lock_settings.py` |
| UI scale regression test | `tests/test_ui_scale.py` |
| Profile hotkey regression test | `tests/test_profile_hotkeys.py` |
| Review hardening regression test | `tests/test_review_hardening.py` |
| Build entry point | `final_build.py` |

## Verification

- Run `C:\Python312\python.exe -m py_compile` for edited Python modules.
- Run focused tests before a full build.
- Run `C:\Python312\python.exe final_build.py` when code changes affect the executable.
- Check the running executable can start and show its main window.

See [diagram index](../docs/diagrams/README.md) for the compact data-flow view.
