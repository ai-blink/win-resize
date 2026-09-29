# Changelog

[English](CHANGELOG.md) | [한국어](CHANGELOG.ko.md) | [中文](CHANGELOG.zh-CN.md) | [日本語](CHANGELOG.ja.md)

This file records notable user-visible changes in WindowResizer. English is the
canonical source for release notes; the Korean, Simplified Chinese, and Japanese
versions carry the same release facts.

## 0.02.0-preview.3 - 2026-09-29

Third preview of the WPF (.NET 10) app, built from source; the distributed
executable is still v0.01.5. Details:
[doc/releases/v0.02.0-preview.3.md](../doc/releases/v0.02.0-preview.3.md).

### Highlights

- Shortcuts page: a global apply-all shortcut and up to three shortcuts per
  profile, each with its own action (apply profile, release locks, toggle always
  on top, toggle auto apply). Every shortcut is listed with its registration result
  and the reason when it fails. Each shortcut is one row (modifier chips, key list, Detect button) saved on its own and checked as it changes; one that cannot be registered gets a red border, the reason and a warning box.
- New Profile > Apply all profiles menu item; the apply-all shortcut runs the same
  path. The apply-all shortcut is imported once from v0.01.5 and stored separately.
- Release locks and auto detection of new windows are not in this preview yet.

### Verification

- .NET build: 0 warnings, 0 errors; 159 tests, all passed; real key presses on
  the running app (against a copy of the profiles) ran the apply-all, apply,
  always-on-top and auto-apply shortcuts, and a conflicting combination was listed
  with its reason.

## 0.02.0-preview.2 - 2026-09-29

Second preview of the WPF (.NET 10) app, built from source; the distributed
executable is still v0.01.5. Details:
[doc/releases/v0.02.0-preview.2.md](../doc/releases/v0.02.0-preview.2.md).

### Highlights

- Overlay buttons on screen: click or dwell to apply a profile to the window you
  were just using; drag, lock, right-click to close, green or red result flash.
- Buttons never take focus; a click no longer raises WindowResizer's own window.
- Hide switch: an eye button that hides and shows all overlay buttons, never
  hides itself, and remembers its position.
- Overlay settings from v0.01.5 carry over the first time.

### Verification

- .NET build: 0 warnings, 0 errors; 112 tests, all passed on repeated runs (a
  focus-dependent live test can be skipped as inconclusive when Windows blocks a
  focus change); real-click checks on the running app for focus, exact placement,
  the hide switch and drag.

## 0.02.0-preview.1 - 2026-09-27

First preview of the rewritten WPF (.NET 10) app, built from source; the
distributed executable is still v0.01.5. Details:
[doc/releases/v0.02.0-preview.1.md](../doc/releases/v0.02.0-preview.1.md).

### Highlights

- Sidebar main window with windows and profiles side by side; search; Enter
  applies to every matching window after a fresh scan.
- Save a window as a new profile (Ctrl+S, prefilled, named after the program);
  overwrite a profile's position with Undo (Ctrl+Z); five-page profile editor.
- Maximized and minimized windows are captured at their normal position.
- Failed saves roll back; unreadable profiles are kept and shown dimmed.
- Closing hides to the tray; Exit program (sidebar, Ctrl+Q, tray) quits.
- Overlay settings page, menu and tray items. The button windows are not in
  this preview yet, nor are the hotkeys, settings and log pages.

### Verification

- .NET build: 0 warnings, 0 errors; 102 tests passed, including live checks on
  real windows, key input, cursor clip and foreground tracking.

## 0.01.5 - 2026-09-25

### Highlights

- Added per-profile overlay buttons with click or dwell activation and a global
  hide switch. The overlay does not steal foreground focus.
- Preserved profile shortcut sets across restarts and added a configurable
  global shortcut for applying all matching profiles.
- Apply All now tries every matching window and reports native operation
  failures instead of treating a failed Win32 call as success.
- Added the .NET 10 WPF solution scaffold and layer-boundary tests as migration
  groundwork. The distributed desktop executable remains the PyQt5 application.

### Verification

- Full tracked Python regression suite: 132 tests passed.
- .NET solution build: 0 warnings and 0 errors; 8 tests passed.
- PyInstaller single-executable build passed.

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
