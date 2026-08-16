# Run Report: Profile Hotkeys

## Outcome

Status: COMPLETE with NEEDS_USER_UI_CHECK for the packaged executable.

## Root Cause

The profile editor rendered and loaded `hotkey_sets`, but omitted that field
when saving. It also always saved the legacy primary shortcut as an empty
string. No application path converted stored profile shortcuts into Windows
`RegisterHotKey` registrations. After that path was added, two runtime defects
remained: `pywin32` returns `None` on successful `RegisterHotKey`, and Qt
consumes `WM_HOTKEY` before timer-based polling can receive it.

## Changed Implementation

- Added `Profile.hotkey_sets` for durable per-profile shortcut storage.
- Saved all enabled shortcut sets and mirrored the first one into the legacy
  fields for existing profiles and views.
- Added parser and a dedicated registration manager without unrelated default
  shortcuts.
- Rebuilt registrations at application start and after profile create, edit,
  and delete operations.
- Connected profile apply, release, and automatic-apply toggle actions to the
  registered shortcut callbacks.
- Treat the `pywin32` `None` return as a successful registration and retain
  its registration ID.
- Receive `WM_HOTKEY` through Qt's native event filter instead of timer
  polling.

## Verification

- `C:\Python312\python.exe tests\test_profile_hotkeys.py` passed 5 tests.
- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'`
  passed 52 tests.
- A temporary Ctrl+Alt+F24 registration and synthetic key input activated the
  manager callback successfully.
- `C:\Python312\python.exe final_build.py` completed and produced
  `dist\WindowResizer.exe` at 38.3 MB with SHA-256
  `6BE36D6AFC9161B0FD1D9B4E8769138EEBCE9AE62D789F46910DED47EBF00AB0`.
- The rebuilt executable replaced `C:\app\WindowResizer.exe`; its SHA-256
  matches the standard build output.

## Remaining UI Check

The installed executable is ready for a live profile Ctrl+Alt+E check. It was
not launched automatically after replacement to avoid competing for the shared
desktop UI.
