# Changelog 1.2.0 — 30/04/2026

## Feature: skip dispositivi inattivi durante load shedding

### Problema
La logica di spegnimento scorreva i dispositivi gestiti in ordine di
priorità e spegneva il primo trovato in stato `on`, anche se il suo
consumo era 0W. Esempio:

```
Priorità 1: Lavatrice    -> switch ON, consumo 0W
Priorità 2: Lavastoviglie -> switch ON, consumo 0W
Priorità 3: Forno         -> switch ON, consumo 3000W
```

Con un debounce alto, il forno veniva spento solo dopo aver inutilmente
"spento" lavatrice e lavastoviglie (che non stavano consumando),
ritardando di minuti la riduzione del carico reale.

### Soluzione
Implementato auto-discovery dei sensori di potenza associati a ciascun
device gestito, tramite `device_id` condiviso nell'`entity_registry`.

All'avvio del `PowerManager` viene popolato il mapping
`switch_entity_id -> power_sensor_entity_id`. La selezione viene fatta
preferendo entità con `device_class="power"`, con fallback su
`unit_of_measurement="W"`.

In `_shed_next_load`, prima di scegliere il target, il consumo del
device viene letto e confrontato con `DEVICE_IDLE_POWER_THRESHOLD`
(10W). I device sotto soglia vengono saltati, scegliendo il primo
device in lista priorità che sta realmente assorbendo potenza.

### Fallback
Se un device non ha sensore di potenza associato (es. switch isolati,
relè senza misuratore), la logica precedente è preservata: lo switch
verrà spento sulla base del solo stato `on`. Viene emesso un warning
nei log al setup per segnalare la situazione.

### Costanti
- Nuova costante `DEVICE_IDLE_POWER_THRESHOLD = 10` in `const.py`.
  Soglia in Watt sotto la quale un device viene considerato inattivo.

### File modificati
- `custom_components/avoidblackout/const.py` — aggiunta costante.
- `custom_components/avoidblackout/power_manager.py` — discovery sensori,
  logica skip device idle in `_shed_next_load`, helper `_get_device_power`.
- `custom_components/avoidblackout/__init__.py` — bump version JS param.
- `custom_components/avoidblackout/manifest.json` — version 1.2.0.
