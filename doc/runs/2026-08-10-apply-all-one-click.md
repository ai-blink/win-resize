# Run Report: Apply All One-Click Fix

## Outcome

Status: COMPLETE. The manual Apply All action now waits for asynchronous window
enumeration to finish before it matches and applies profiles. A single click
therefore uses the current window list, including newly opened target windows.

## Scope

- Preserve asynchronous window enumeration in the main window.
- Continue profile application only after the matching refresh completes.
- Add a regression test that proves application is deferred until fresh windows
  arrive.

## Changed Implementation

- `src/gui/main_window.py`
- `tests/test_apply_all_profiles.py`

## Verification

- `C:\Python312\python.exe -m py_compile src\gui\main_window.py tests\test_apply_all_profiles.py` passed.
- `C:\Python312\python.exe tests\test_apply_all_profiles.py` passed 2 tests.
- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'` passed 36 tests.
- `C:\Python312\python.exe final_build.py` rebuilt `dist\WindowResizer.exe`.

## Follow-up

- Manually verify one-click application against a target window opened after
  WindowResizer starts.
