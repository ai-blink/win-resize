# Run Report: Window Geometry Regression

## Outcome

Status: COMPLETE.

## Scope

- Keep the pre-application Qt high-DPI configuration enabled.
- Fit the initial main window to the primary screen work area.
- Calculate edge presets from the selected target window monitor work area.
- Convert native profile preview geometry at the Qt boundary only.

## Changed Implementation

- `src/gui/main_window.py`
- `tests/test_window_geometry.py`

## Compatibility

Saved profile x, y, width, and height values remain native Win32 values.
No profile migration or global DPI scaling was applied.
The stored `monitor_index` behavior is unchanged because its coordinate policy
requires a separate compatibility decision.

## Verification

- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_window_geometry.py'` passed 5 tests.
- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_profile_preview_and_auto_apply.py'` passed 12 tests.
- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'` passed 32 tests.
- Pre-application high-DPI startup reported an available work area of
  `1864x1080` and an initial window of `1150x800` at `(413, 140)`.
