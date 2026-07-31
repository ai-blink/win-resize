# Development Decisions

## Vision

- D-001: Preserve direct, profile-driven window control as the primary product behavior.

## Layer Boundaries

- D-002: GUI owns user choices; core profile logic owns configuration application and constraint release.

## Executor Policy

- D-003: Apply saved geometry before enabling a position lock so the lock preserves the selected profile position.

## Security

- D-004: Keep local profiles, logs, and generated diagnostics out of source control.

## Workflow

- D-005: Use focused Python tests and a PyInstaller build for UI-impacting changes.

## Infrastructure

- D-006: `ThemeManager` is the source of runtime palette values and Qt-wide dialog styling.
- D-007: Persist profiles through a flushed temporary file and atomic replacement; keep a readable backup as recovery input.
- D-008: Release cursor confinement through the native `ClipCursor(NULL)` call because the PyWin32 wrapper requires a rectangle.
