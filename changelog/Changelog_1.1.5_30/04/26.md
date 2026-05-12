# Changelog 1.1.5 — 30/04/2026

## Fix: dispatch `ll-rebuild` dopo `customElements.define`

### Problema
Anche dopo il fix 1.1.4 (registrazione path async), l'errore
"Custom element doesn't exist: avoidblackout-card" continuava a comparire
al refresh della dashboard. Il file JS veniva caricato correttamente (HTTP
200) ma Lovelace tentava il render della card PRIMA che il browser avesse
eseguito `customElements.define`.

### Soluzione
Aggiunto dispatch dell'evento `ll-rebuild` su `window` subito dopo la
chiamata a `customElements.define("avoidblackout-card", ...)`. Lovelace
ascolta questo evento e ricostruisce le card che avevano fallito al primo
render, eliminando l'errore.

### File modificati
- `custom_components/avoidblackout/www/avoidblackout-card.js` — dispatch
  `ll-rebuild` dopo `customElements.define`.
- `custom_components/avoidblackout/__init__.py` — bump version param JS.
- `custom_components/avoidblackout/manifest.json` — version 1.1.5.
