

const TRANSLATIONS = {
  it: {
    status_monitoring: "Protetto",
    status_waiting: "Attesa...",
    status_shedding: "Emergenza",
    entity_not_found: "Entità non trovata",
    current_consumption: "Consumo Attuale",
    limit_threshold: "Soglia limite",
    disconnected_loads: "CARICHI SCOLLEGATI",
    reset: "RIPRISTINA",
    error_no_entity: "Devi definire un'entità di stato AvoidBlackout",
    card_name: "AvoidBlackout Monitor",
    card_description: "Card premium per monitorare il sovraccarico e gestire i distacchi dei carichi."
  },
  en: {
    status_monitoring: "Protected",
    status_waiting: "Waiting...",
    status_shedding: "Emergency",
    entity_not_found: "Entity not found",
    current_consumption: "Current Consumption",
    limit_threshold: "Limit threshold",
    disconnected_loads: "DISCONNECTED LOADS",
    reset: "RESET",
    error_no_entity: "You must define an AvoidBlackout state entity",
    card_name: "AvoidBlackout Monitor",
    card_description: "Premium card to monitor overload and manage load shedding."
  }
};

class AvoidBlackoutCard extends HTMLElement {
  set hass(hass) {
    const lang = hass.language || "en";
    const t = TRANSLATIONS[lang] || TRANSLATIONS["en"];

    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content"></div>
        </ha-card>
        <style>
          .card-header-container { display: flex; justify-content: space-between; align-items: center; padding-bottom: 16px; }
          .card-name { font-weight: bold; font-size: 1.1em; color: var(--primary-text-color); }
          .status-badge { padding: 4px 12px; border-radius: 12px; font-size: 0.8em; font-weight: bold; text-transform: uppercase; }
          .monitoring { background: rgba(76, 175, 80, 0.1); color: #4caf50; }
          .waiting { background: rgba(255, 152, 0, 0.1); color: #ff9800; animation: blink 1.5s infinite; }
          .shedding { background: rgba(244, 67, 54, 0.1); color: #f44336; }
          
          .power-info { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
          .power-row { display: flex; justify-content: space-between; font-size: 0.9em; color: var(--secondary-text-color); }
          .power-total { font-size: 1.5em; font-weight: bold; color: var(--primary-text-color); }
          
          .progress-container { background: var(--secondary-background-color); height: 8px; border-radius: 4px; overflow: hidden; position: relative; }
          .progress-bar { height: 100%; transition: width 0.5s ease, background-color 0.5s ease; }
          
          .entities-list { margin-top: 16px; border-top: 1px solid var(--divider-color); padding-top: 12px; }
          .entities-title { font-weight: bold; font-size: 0.9em; margin-bottom: 8px; color: #f44336; }
          .entity-chip { display: inline-flex; align-items: center; background: rgba(244, 67, 54, 0.1); color: #f44336; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; margin: 2px; }
          
          .actions { display: flex; justify-content: flex-end; margin-top: 12px; }
          mwc-button { --mdc-theme-primary: var(--primary-text-color); }

          @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        </style>
      `;
      this.content = this.querySelector(".card-content");
    }

    const entityId = this.config.entity;
    const stateObj = hass.states[entityId];

    if (!stateObj) {
      this.content.innerHTML = `<div style="color: red;">${t.entity_not_found}: ${entityId}</div>`;
      return;
    }

    const state = stateObj.state;
    const attr = stateObj.attributes;
    const power = attr.total_power || 0;
    const threshold = attr.threshold || 1;
    const pct = Math.min((power / threshold) * 100, 100);
    const entities = attr.shutdown_entities || [];

    let color = "#4caf50";
    if (pct > 70) color = "#ff9800";
    if (pct > 90 || state === 'shedding') color = "#f44336";

    const stateMap = {
      'monitoring': t.status_monitoring,
      'waiting': t.status_waiting,
      'shedding': t.status_shedding
    };

    try {
      this.content.innerHTML = `
        <div class="card-header-container">
          <div class="card-name">${this.config.name || "AvoidBlackout"}</div>
          <div class="status-badge ${state}">${stateMap[state] || state}</div>
        </div>
        
        <div class="power-info">
          <div class="power-row">${t.current_consumption} <span class="power-total">${power}W</span></div>
          <div class="progress-container">
            <div class="progress-bar" style="width: ${pct}%; background-color: ${color};"></div>
          </div>
          <div class="power-row">${t.limit_threshold}: ${threshold}W <span>${Math.round(pct)}%</span></div>
        </div>

        ${entities.length > 0 ? `
          <div class="entities-list">
            <div class="entities-title">${t.disconnected_loads}</div>
            <div>
              ${entities.map(e => `
                <div class="entity-chip">
                  <ha-icon icon="mdi:power-plug-off" style="--mdc-icon-size: 14px; margin-right: 4px;"></ha-icon>
                  ${hass.states[e]?.attributes?.friendly_name || e}
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div class="actions">
          <mwc-button id="reset-button">
            <ha-icon icon="mdi:refresh" style="--mdc-icon-size: 18px; margin-right: 4px;"></ha-icon>
            ${t.reset}
          </mwc-button>
        </div>
      `;

      const btn = this.shadowRoot ? this.shadowRoot.querySelector("#reset-button") : this.querySelector("#reset-button");
      if (btn) {
        btn.onclick = () => this._reset(hass);
      }
    } catch (e) {
      console.error("AvoidBlackoutCard Error:", e);
    }
  }

  _reset(hass) {
    hass.callService("avoidblackout", "reset_history", {});
  }

  setConfig(config) {
    if (!config.entity) {
      const lang = (navigator.language || "en").split("-")[0];
      const t = TRANSLATIONS[lang] || TRANSLATIONS["en"];
      throw new Error(t.error_no_entity);
    }
    this.config = config;
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return {
      entity: "sensor.avoidblackout_status",
      name: "Monitor Energetico"
    }
  }
}

// Registrazione elemento custom con controllo per evitare duplicati
if (!customElements.get("avoidblackout-card")) {
  customElements.define("avoidblackout-card", AvoidBlackoutCard);
}

// Registrazione nel selettore delle card
window.customCards = window.customCards || [];

const lang = (navigator.language || "en").split("-")[0];
const t = TRANSLATIONS[lang] || TRANSLATIONS["en"];

// Verifica che non sia già presente per evitare duplicati nel selettore
if (!window.customCards.some(card => card.type === "avoidblackout-card")) {
  window.customCards.push({
    type: "avoidblackout-card",
    name: "AvoidBlackout Card", // Cambiato da Monitor a Card per coerenza con README
    description: t.card_description,
    preview: true,
  });
}

