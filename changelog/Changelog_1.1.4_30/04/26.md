# Changelog 1.1.4 — 30/04/2026

## Fix: "Custom element not found: avoidblackout-card" al refresh dashboard

### Problema
Al refresh della pagina Home Assistant (o al cambio dashboard), la card
`avoidblackout-card` non veniva trovata nel 99% dei casi, mostrando l'errore
"Errore di configurazione: Custom element not found: avoidblackout-card".
Funzionava solo al primo caricamento dopo restart di HA.

### Causa
In `__init__.py` la registrazione del percorso statico per servire
`avoidblackout-card.js` usava un branch condizionale che preferiva l'API
sincrona deprecata `hass.http.register_static_path` quando disponibile.

Su HA 2024.7+ questa API è deprecata e in alcuni scenari il path non risulta
servito in tempo rispetto al primo render della dashboard innescato da
`add_extra_js_url`, causando un 404 sul file JS e quindi il mancato
`customElements.define("avoidblackout-card", ...)`.

### Soluzione
Rimosso il branch `hasattr(hass.http, "register_static_path")` e usata sempre
l'API async `hass.http.async_register_static_paths` con `StaticPathConfig`.
Questa API è quella raccomandata su HA 2024.7+ e garantisce che il path sia
registrato e disponibile prima che il browser tenti di caricare lo script.

### Bump versione
Versione bumpata da 1.1.3 → 1.1.4 in `manifest.json` e nel parametro `?v=`
passato a `add_extra_js_url` in `__init__.py`. Il bump forza l'invalidazione
della cache del browser per i client che hanno già una versione precedente
del JS in cache.

### File modificati
- `custom_components/avoidblackout/__init__.py` — rimosso branch deprecato,
  bump versione JS a 1.1.4.
- `custom_components/avoidblackout/manifest.json` — version 1.1.4.
