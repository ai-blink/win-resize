# Run Report: Single-Instance Startup Protection

## Outcome

Status: COMPLETE. WindowResizer now permits one main application instance per
Windows session. A duplicate launch shows a short notice and exits.

## Scope

- Add a named Windows mutex to the primary application entry point.
- Release the mutex on normal exit and startup exceptions.
- Add focused regression coverage for existing-instance and release behavior.

## Changed Implementation

- `run_gui.py`
- `tests/test_review_hardening.py`

## Verification

- `C:\Python312\python.exe -m py_compile run_gui.py tests\test_review_hardening.py` passed.
- `C:\Python312\python.exe tests\test_review_hardening.py` passed 11 tests.
- `C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'` passed 35 tests.
- Native mutex check verified that the first guard acquires the mutex, a second
  guard is rejected, and the mutex can be acquired after release.
- `C:\Python312\python.exe final_build.py` rebuilt `dist\WindowResizer.exe`.

## Follow-up

- None for this scope.
