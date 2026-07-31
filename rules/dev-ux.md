# UI and UX Rules

## Interface Principles

- A checkbox must describe its exact effect and must not silently enable a related constraint.
- Profiles show position locking and mouse confinement as separate options.
- Destructive actions require a readable confirmation dialog in every supported theme.
- Tables must provide readable normal, selected, hover, and alternate-row states.

## Theme Rules

- Use values from `ThemeManager` and `ThemeElement`; do not add fixed dark or light colors to feature styles.
- Apply the active Qt palette globally so dialogs not created by a custom helper remain readable.
- In system-theme mode, derive the initial palette from the detected Windows application theme and continue monitoring it.
- Choose highlighted text from the active selection brightness so custom themes cannot inherit an unreadable background color.
- Reapply custom widget styles when the theme changes.
- Verify light, dark, and high-contrast variants after theme-facing edits.

## Relevant Components

| Component | Owner | User-visible state |
|---|---|---|
| Main window table | `main_window.py` | normal, alternate, hover, selected |
| Profile editor | `profile_editor.py` | saved flags and active theme |
| Confirmation dialogs | `theme_manager.py` | title, message, buttons |
| Manual profile apply | `main_window.py` | status message when no window matches |

## Performance

- Do not add polling or forced locking unless the profile option is enabled.
- Keep theme updates local to the existing Qt event loop.
