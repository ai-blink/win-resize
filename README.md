# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer is a Windows desktop application for finding application windows,
moving or resizing them, and repeatedly applying saved window profiles.

Current release: 0.02.0 (rewritten in WPF on .NET 10; the earlier PyQt5 app is v0.01.5)

## Features

- List running windows with search, and apply a profile to the matching windows at once, from a
  button, a menu, Enter or a global shortcut.
- Save a window's position and size as a profile (Ctrl+S), overwrite a profile's place from a window
  with undo, and edit profiles in a sidebar editor.
- Match profiles by full executable path, process name, window title (contains, exact, regex) or a
  combination, so applications with the same filename can be told apart.
- Lock a profile's position: a window that is dragged away is put back to where it was applied.
- Confine the mouse to a profile's window while that window is in front, with an escape key.
- Apply a profile automatically to a matching window that appears after the app starts.
- Overlay buttons: floating buttons, each with its own saved window place and size, that move the
  window you were just using there. Buttons have a properties window with an actual-size preview,
  can take a place from the last window or from a window you point at on screen.
- Global shortcuts per profile (several combinations, several actions), an apply-all shortcut and an
  always-on-top toggle.
- Light, dark and follow-system themes (Windows high contrast is honoured), an app scale from 75% to 250%, Korean or English
  labels, start with Windows, and a log page.
- Stays in the system tray when the main window is closed, and starts only one copy per Windows
  session (a second start brings the first window forward).

## Not in 0.02.0 yet

- The profile preview outline that PyQt5 showed for three seconds.
- Chinese and Japanese labels in the app (Korean and English only; the documents are in four languages).
- An installer and an update mechanism. The release is one self-contained executable.

## Requirements

- Windows 10 or Windows 11, 64-bit. The release executable carries its own .NET runtime, so nothing
  else has to be installed.

Windows that run with administrator privileges cannot be controlled by a standard-privilege
WindowResizer. Run WindowResizer at the same privilege level when necessary.

## Run the release

Download `WindowResizer.exe` from the GitHub release and run it. Profiles are read from and written
to the `profiles` folder next to the executable; settings are kept under
`HKCU\Software\WindowResizer\Next`. Details are in the [installation guide](docs/INSTALLATION.md).

## Build from source

~~~powershell
dotnet build next\WindowResizer.slnx
dotnet test next\WindowResizer.slnx
powershell -NoProfile -File next\tools\publish.ps1
~~~

The last command writes the single-file executable to `next\publish\win-x64\`.
The .NET 10 SDK is required to build.

## Documentation

The installation and user guides are Korean. Release notes and the changelog are in English, Korean,
Simplified Chinese and Japanese:

- [Installation and running guide (Korean)](docs/INSTALLATION.md)
- [User guide (Korean)](docs/USER_GUIDE.md)
- [Changelog: English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)
- Release notes: `doc/releases/`

## Repository layout

- next/: the WPF application (src/ for the app, tests/, tools/ for publishing)
- doc/, docs/: release notes, changelog and user documentation
- src/, run_gui.py, final_build.py, tests/: the earlier PyQt5 application (v0.01.5, tag `last-pyqt5-stable`), kept for reference
