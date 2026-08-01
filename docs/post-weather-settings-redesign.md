# Post-weather Settings redesign

## Status and timing

The weather-provider work has now been built and physically validated on the
bedroom Raspberry Pi. This Settings redesign is therefore the next active
interface pass before final release preparation.

Weather was the final major subsystem. The work below is consolidation and
interface polish, not another appliance subsystem.

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
- The forecast provider's dedicated validated save-and-refresh flow.
- The on-screen touch keyboard and its keyboard-safe alarm save positioning.
- Current URL/state ownership and manual screen leases.
- Accessible labels, focus order and reduced-motion behaviour.

## Consolidation included in this pass

- Replace the obsolete static alarm configuration shell with a clean mount point.
- Give one Settings composition layer ownership of each drill-down screen.
- Retire horizontal-tab handover logic rather than wrapping it inside the new UI.
- Reduce scripts that poll for or repeatedly reshape DOM created by another
  Settings script.
- Load Settings-only clients only on the Settings route where practical.
- Preserve the existing backend APIs instead of coupling the new navigation to
  configuration storage.

## Design questions for the pass

- Whether drill-down sections should use separate URLs, history state, or one
  Settings route with an internal navigation stack.
- Whether search is useful at this project size.
- Which frequently used controls deserve summary values on the top-level rows.
- Whether Advanced should require a deliberate extra tap or warning treatment.
- How Settings should return to the previously visible subsection after a
  dashboard restart or temporary Alarm takeover.

The first implementation step should establish the top-level list and navigation
stack while leaving the existing section contents and save behaviour intact.
After that stable shell is physically validated, individual sections can be
simplified and consolidated incrementally.
