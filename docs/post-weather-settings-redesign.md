# Post-weather Settings redesign reminder

## Timing

Revisit Settings **after the weather-provider work is complete** and before final
release approval.

Weather remains the final major subsystem. This is a subsequent interface-polish
pass, not a reason to interrupt or redesign the weather implementation midway.

## Direction

Replace the current horizontal top-tab system with an **iPhone-style Settings
interface**:

```text
Settings
├── General              >
├── Weather              >
├── Alarms               >
├── AirPlay              >
├── Audio                >
├── Plexamp              >
├── Advanced             >
└── About                >
```

Selecting a row should open a dedicated drill-down screen with a clear Back
control, grouped list sections and touchscreen-sized rows. The top-level page
should remain easy to scan without fitting eight horizontal tabs across the
screen.

## Behaviour to preserve

- General Settings autosave and its visible Saving/Saved/failed feedback.
- The dedicated validated **Save alarms** flow for the JSON alarm model.
- Separate alarm-sound safety settings and Advanced alarm diagnostics.
- Live Audio controls and their existing dedicated APIs.
- The on-screen touch keyboard and its keyboard-safe alarm save positioning.
- Current URL/state ownership and manual screen leases.
- Accessible labels, focus order and reduced-motion behaviour.

## Design questions for that pass

- Whether drill-down sections should use separate URLs, history state, or one
  Settings route with an internal navigation stack.
- Whether search is useful at this project size.
- Which frequently used controls deserve summary values on the top-level rows.
- Whether Advanced should require a deliberate extra tap or warning treatment.
- How Settings should return to the previously visible subsection after a
  dashboard restart or temporary Alarm takeover.

This note is intentionally a reminder and scope marker, not an implementation
specification. Review the working Settings screen and agree the detailed visual
design after weather is finished.
