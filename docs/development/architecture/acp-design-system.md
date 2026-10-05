# ACP component / design-token architecture

**Status:** Phase A foundation in progress  
**Scope:** ACP-owned browser surfaces only. Native Plexamp remains a separate application/workspace.

## Purpose

The long-lived Surface Host removes the old page-navigation boundary. The next boundary is presentation ownership:

```text
ACP data / service snapshots
        ↓
surface presenters / controllers
        ↓
reusable ACP component contracts
        ↓
semantic component tokens
        ↓
palette tokens / daytime themes
        ↓
application surfaces
```

Application CSS should own layout and feature-specific presentation. It should not need to know the literal Classic-Dark colour used by an ordinary control, the standard panel radius, or which palette variable represents foreground text.

## Existing palette authority

The accepted palette remains authoritative:

- `--panel`
- `--panel-border`
- `--text`
- `--muted`
- `--accent`
- `--accent-strong`
- the non-Classic `--acp-theme-*` variables in `daytime-themes.css`

The component layer must derive from that authority rather than inventing a second independent colour system.

## Semantic token layer

`app/static/css/acp-design-tokens.css` is loaded before the shared/page component styles.

The first token families are:

- semantic palette aliases such as `--acp-color-surface`, `--acp-color-border`, `--acp-color-text` and accent aliases;
- neutral control/card fills that preserve the accepted Classic-Dark values exactly during incremental migration;
- reusable radii for panel/card/control/pill geometry;
- common elevation tokens.

The token file deliberately contains no page selectors. It is a vocabulary, not another override sheet.

## First migrated primitives

The initial low-risk slice routes existing accepted values through the token boundary without intended visual change:

- shared `.panel`;
- shared `.weather-card`;
- shared `.button`;
- AirPlay top-level now-playing/info surface colour/border/radius;
- Weather detail-panel surface colour/border;
- News rail/content/ticker surface colour/border/elevation.

Feature geometry remains in its existing page stylesheet.

## Migration rules

1. **Preserve the accepted look first.** Tokenisation is not permission to redesign a component.
2. **Palette and semantics are different.** Ordinary chrome may use shared palette tokens; warning/error/success states keep semantic ownership.
3. **Do not force false reuse.** Components with different interaction or geometry contracts stay separate even if their current paint is similar.
4. **No page-specific selectors in the token file.**
5. **No service/data authority in components.** Components render state supplied by their surface/controller.
6. **Existing theme-closure layers remain until their covered components migrate.** Delete an override only when equivalent theme behaviour is provided by the component/token contract and physically accepted.
7. **Native Plexamp is excluded.** ACP may theme its own shell/navigation around Plexamp, but not the native Plexamp application itself.

## Inventory / next candidates

The current CSS inventory shows useful repeated contracts in these groups:

- surface/card containers;
- pill/status indicators;
- touch rows and ordinary buttons;
- text/select/toggle/range form controls;
- modal/dialog chrome;
- custom scrollbar rails/thumbs;
- headers/kickers/secondary text.

Specialised audio faders/knobs, seven/fourteen-segment displays, AirPlay artwork geometry, Weather compass/gauges and Alarm takeover presentation are not first-pass generic components.

## Acceptance

Each migration slice must keep:

- Classic Dark visually stable;
- all curated daytime themes palette-correct;
- Astronomy/night treatment ownership intact;
- 1280×720 fit and touch targets unchanged;
- mounted-surface lifecycle behaviour unchanged.

Static regression tests pin token load order and the first migrated primitives. Physical checking should compare representative surfaces/themes rather than requiring every page component to be exhaustively inspected after each token-only refactor.


## Second bounded migration

The first token slice is physically accepted on the commissioned Pi in both Classic Dark and a non-Classic daytime theme.

The second slice extends the boundary to ordinary interaction chrome:

- Settings native fields and ACP custom-select triggers share field border/fill/focus/radius tokens.
- Settings field containers retain their original 7% white neutral fill through a dedicated token rather than being flattened into the 8% generic card fill.
- Settings subpage rows and News touch surfaces consume neutral component fill tokens while their geometry remains local.
- News and Weather status badges use the shared pill radius and semantic palette aliases; warning/stale colours remain component semantics.
- News, Weather Forecast and Rain History custom rails share only geometry (8 px track, 4 px thumb, 42 px minimum thumb). Their accepted page/theme colour treatment remains local.
- Kiosk-safe modal ordinary text/accent paint uses semantic palette aliases; modal layout, surface fill and elevation remain specialised.

This illustrates the migration rule: **share stable semantics and geometry only where the existing contracts are already equivalent; do not create fake reuse by normalising visibly different components.**
