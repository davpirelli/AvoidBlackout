# Changelog 1.2.1 — 30/04/2026

## Fix: registrazione card come Lovelace dashboard resource

### Problema
Anche dopo i fix 1.1.4 (path async) e 1.1.5 (`ll-rebuild`), al refresh
della dashboard continuava a comparire l'errore
"Custom element doesn't exist: avoidblackout-card".

Causa: `add_extra_js_url` aggiunge lo script al manifest del frontend ma
non garantisce che venga eseguito PRIMA del primo render della dashboard.
Lovelace tenta di istanziare `avoidblackout-card` mentre il browser sta
ancora scaricando il JS, e l'errore viene mostrato sincronicamente
senza retry.

### Soluzione
Aggiunta registrazione della card come **Lovelace dashboard resource**
via storage collection (`hass.data["lovelace"].resources`). Le resources
Lovelace vengono caricate in modo bloccante prima del bootstrap della
dashboard, garantendo che `customElements.define` sia chiamato prima
del primo render.

Logica implementata in `_async_register_lovelace_resource`:
- Carica resources collection se non già caricata.
- Match per URL base (senza query string) per riconoscere registrazioni
  esistenti di versioni precedenti.
- Update in-place se URL cambia (cache bust su nuova release).
- Create new resource se assente.
- Catch generico con warning per dashboard in modalità YAML (in cui la
  storage collection non è scrivibile): in quel caso resta il fallback
  di `add_extra_js_url`.

Resource registrata con `res_type: js` (la card è classic JS, non un
ES module).

### File modificati
- `custom_components/avoidblackout/__init__.py` — registrazione resource
  + nuovo helper `_async_register_lovelace_resource`.
- `custom_components/avoidblackout/manifest.json` — version 1.2.1.
