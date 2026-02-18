# AvoidBlackout ⚡️ Safe Power Manager for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-1.0.3-orange.svg?style=for-the-badge)

**AvoidBlackout** è un'integrazione intelligente per Home Assistant progettata per prevenire il distacco del contatore elettrico per sovraccarico. Monitora in tempo reale i consumi della tua casa e scollega automaticamente i carichi non prioritari quando ti avvicini alla soglia limite.

![Card Preview](/assets/card-carichi-off.png)
---

## ✨ Caratteristiche Principali

- **Protezione Attiva**: Monitora i sensori di potenza e interviene prima che scatti il differenziale.
- **Gestione Priorità**: Decidi tu l'ordine di spegnimento dei dispositivi.
- **Debounce Intelligente**: Evita spegnimenti accidentali dovuti a picchi momentanei.
- **Card Premium**: Una bellissima interfaccia Lovelace per monitorare lo stato e ripristinare i carichi con un click.
- **Notifiche Intelligenti**: Blueprint incluso per ricevere avvisi immediati su smartphone o smart speaker.
- **Modalità Test**: Verifica la logica di distacco senza spegnere realmente nulla.

---

## Interfaccia Grafica

L'integrazione include una **Custom Card** moderna che si adatta automaticamente al tema di Home Assistant:

![Card Preview](/assets/card.png)
![Card Preview](/assets/card-carichi-off.png)
![Card Preview](/assets/animation.gif)

---

## Installazione via HACS

1. Apri **HACS** in Home Assistant.
2. Vai su **Integrazioni** e clicca sui tre puntini in alto a destra.
3. Seleziona **Repository Personalizzati**.
4. Incolla l'URL di questo repository e seleziona la categoria `Integrazione`.
5. Clicca su **Installa**.
6. Riavvia Home Assistant.

---

## Configurazione

Dopo l'installazione, aggiungi l'integrazione dalla pagina **Impostazioni > Dispositivi e Servizi**:

1. Cerca **AvoidBlackout**.
2. **Sensori**: Seleziona uno o più sensori di potenza (W). Se ne selezioni più di uno, verranno sommati (utile se hai più linee o pinze amperometriche).
3. **Soglia**: Imposta la potenza massima contrattuale (es. 3300 per 3kW).
4. **Debounce**: Tempo di attesa (secondi) prima di intervenire dopo il superamento della soglia.
5. **Priorità**: Seleziona i dispositivi da gestire nell'ordine in cui desideri che vengano spenti.

---

## Card Lovelace

La card viene registrata automaticamente. Per aggiungerla al tuo pannello:

```yaml
type: custom:avoidblackout-card
entity: sensor.avoidblackout_status
name: "Monitor Energetico" # Opzionale
```

---

## Blueprint (Notifiche)

Ho incluso un Blueprint per semplificare la creazione di automazioni che ti avvisano quando inizia un distacco carichi:

1. Vai in **Impostazioni > Automazioni e Scene > Blueprint**.
2. Cerca **Load Shedding Notification (AvoidBlackout)**.
3. Clicca su **Crea Automazione**.
4. Seleziona il sensore di stato e i servizi di notifica (es. `notify.mobile_app_tuo_cellulare`).

---

## Servizi

L'integrazione espone due servizi utili:

- `avoidblackout.reset_history`: Riattiva tutti i carichi che erano stati spenti e riporta il sistema in modalità monitoraggio.
- `avoidblackout.simulate_overload`: Forza una procedura di distacco (utile per testare le automazioni senza superare realmente la soglia).

---

## Multilingua
Attualmente supportato:
- 🇮🇹 Italiano
- 🇬🇧 English

---

### Sviluppato con ❤️ per la Community di Home Assistant.

*Se ti piace questo progetto, offrimi un caffè ☕️ o lascia una ⭐ su GitHub!*
