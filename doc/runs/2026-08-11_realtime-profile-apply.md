# Run Report: Realtime Profile Application

## Outcome

Status: COMPLETE. A real-time profile now starts new-window detection from its
own opt-in toggle, and a maximized target is restored before its saved normal
window geometry is applied.

## Scope

- Restore a maximized window before normal position and size application.
- Use the PyWin32-supported `GetWindowPlacement` API for maximized-state
  detection.
- Start or stop new-window detection from active profiles that opt in to
  real-time position and size maintenance.
- Clarify the profile editor toggle label and add focused regression coverage.

## Root Cause

The packaged PyWin32 `win32gui` module does not expose `IsZoomed`. Calling it
aborted profile application for every matching window. Separately, saving a
real-time profile started monitoring only for windows already open; the global
new-window monitor remained stopped, so a later Blender window was not found.

## Changed Implementation

- `src/core/profile_manager.py`
- `src/gui/main_window.py`
- `src/gui/profile_editor.py`
- `tests/test_profile_preview_and_auto_apply.py`

## Verification

- `C:\Python312\python.exe -m py_compile src\gui\main_window.py tests\test_profile_preview_and_auto_apply.py` passed.
- Focused toggle regression tests passed:
  - `test_enabled_realtime_profile_starts_new_window_monitor`
  - `test_disabled_realtime_profile_does_not_start_new_window_monitor`
- `C:\Python312\python.exe final_build.py` created
  `dist\WindowResizer.exe` successfully.
- Packaged 10-second startup smoke check created a main window successfully.
- With `dist\profiles\profiles.json` containing one active real-time profile,
  the packaged log recorded new-window monitoring startup.

## Follow-up

- Manually open one new Blender window and confirm that it reaches the saved
  geometry after its startup delay, then returns after a user move or resize.
