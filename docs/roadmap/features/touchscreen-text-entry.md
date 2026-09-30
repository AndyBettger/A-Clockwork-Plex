# Touchscreen text entry

**Status:** COMPLETE #91; migration impact tracked by #94

## Accepted scope

- Shared ACP touchscreen keyboard with one-shot Shift and theme-aware presentation.
- Plexamp Headless Search and ordinary supported text fields physically accepted.
- Narrow local bridge remains permission-free and excludes login/password fields.

## Future dependency

The accepted keyboard is browser/DOM-owned. Native Plexamp cannot reuse it directly; #94 must separately prove native/system-level text entry before Headless can be retired.

## Detailed authority

- `../../development/architecture/touchscreen-text-entry.md`
