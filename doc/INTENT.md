# WindowResizer Intent

WindowResizer is a Windows desktop application for finding application windows,
moving or resizing them, and repeatedly applying saved profiles.

The current release target is a dependable desktop UI with readable light and
dark themes. Profiles can optionally keep a window at its saved position after
they are applied. Cursor confinement remains a separate option.

Profile changes must not replace a valid saved file until the new data is
durably written. If a prior-version write left the primary file unreadable, the
application recovers the last backup. System-theme mode uses the detected
Windows theme, and a profile action must explain when no matching window exists.

Non-goals for this release are a public REST API, plugin platform, documented
command-line interface, and background automation claims not backed by the
current application.
