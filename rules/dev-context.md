# Resume Context

- Active goal: complete the review-hardening release check after the running `dist\WindowResizer.exe` releases its file lock.
- Branch state: stay on `main`; keep review-hardening changes separate from unrelated existing untracked files.
- Latest code evidence: `C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'` passed 23 tests on 2026-07-31.
- Latest native evidence: `ctypes.windll.user32.ClipCursor(None)` returned `True` on 2026-07-31.
- Latest build evidence: `C:\Python312\python.exe final_build.py` reached PyInstaller EXE assembly, then stopped because `dist\WindowResizer.exe` was locked by a running process.
- Immediate next step: close the running executable, rerun the official build, and record the packaged smoke result.
- Constraints: do not commit build output, virtual environments, local profiles, logs, generated diagnostics, or unrelated existing untracked files.
- Read first: `rules/dev-progress.md`, `doc/runs/2026-07-31_review-hardening.md`, and `rules/dev-roadmap.md`.
