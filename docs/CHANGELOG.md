# Changelog

[English](CHANGELOG.md) | [한국어](CHANGELOG.ko.md) | [中文](CHANGELOG.zh-CN.md) | [日本語](CHANGELOG.ja.md)

This file records notable user-visible changes in WindowResizer. English is the
canonical source for release notes; the Korean, Simplified Chinese, and Japanese
versions carry the same release facts.

## 0.01.4 - 2026-08-10

### Hotfixes

- Apply All now waits for asynchronous window-list refresh to complete before
  applying profiles to the current window list.
- Windows opened after WindowResizer starts can be matched and updated with one
  Apply All action.

### Verification

- tests/test_apply_all_profiles.py: 2 tests passed.
- Full tracked regression suite: 36 tests passed.
- final_build.py: dist/WindowResizer.exe built successfully.

## 0.01.3 - 2026-08-04

### Hotfixes

- Added a per-Windows-session named mutex to prevent duplicate application
  instances.
- Starting the app while it is already running shows a message and exits without
  creating another main window.
- Released the mutex handle on normal shutdown and when startup fails.

### Verification

- tests/test_review_hardening.py: 11 tests passed.
- Full tracked regression suite: 35 tests passed.
- Verified native mutex acquisition, duplicate rejection, and reacquisition after
  release.
- final_build.py: dist/WindowResizer.exe built successfully.

## 0.01.1 - 2026-07-31

### Hotfixes

- Made profile saves atomic and added recovery from the last valid backup.
- Releasing position lock or cursor confinement now also releases the active
  restriction.
- Corrected Win32 cursor-confinement release behavior on multi-monitor systems.
- Detected the system theme on first launch and ensured readable text for custom
  selection colors.
- Showed a status-bar result when a profile has no matching window.
- Applied high-DPI settings before QApplication creation and allowed the
  official build to succeed when the source icon is unavailable.

## 0.01 - 2026-07-31

### Initial release improvements

- Improved window identity data so Apply All can match profiles by executable
  path.
- Increased profile toolbar button and status-label height to prevent text from
  being clipped by theme padding.
- Changed title-bar close to hide the app in the system tray and added explicit
  exit actions in the status bar and tray menu.
- Select the newly added row after creating a profile from a window so it can be
  deleted immediately if needed.
- Report profile-store deletion failures instead of hiding their cause.
- Added full executable paths as a profile match criterion and made them the
  recommended identifier instead of process IDs.
- Enabled only the match inputs relevant to the selected profile strategy and
  added a command to capture the selected window's executable path.
- Display the target filename and full path for path-based profiles in the
  profile list.
- Added a three-second layout preview that does not move or resize real windows.
- Added per-profile automatic application for new windows and main-screen
  controls to start and stop detection.
- Preserved each profile's selected match strategy when automatic detection
  applies profiles.
- Added an optional profile position lock.
- Preserved existing advanced settings when profiles are edited.
- Allowed active position locks and cursor constraints to be released.
- Refreshed the main window and profile editor from the active theme palette.
- Improved visibility for alternating table rows and standard Qt confirmation
  dialogs.

### Verification

- tests/test_profile_editor_lock_settings.py: 3 tests passed.
- tests/test_profile_preview_and_auto_apply.py: 8 tests passed.
- tests/test_profile_deletion.py: 1 test passed.
- tests/test_close_to_tray.py: 1 test passed.
- tests/test_profile_button_bar_layout.py: 1 test passed.
- tests/test_apply_all_profiles.py: 1 test passed.
- final_build.py: dist/WindowResizer.exe built successfully.
