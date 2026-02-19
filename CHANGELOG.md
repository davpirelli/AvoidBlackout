# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.1.0] - 2026-02-19

### Added
- New `number` entities (`max_threshold`, `debounce_time`) to configure the integration live from the HA dashboard, without restarting.
- `update_threshold()` and `update_debounce()` methods on `PowerManager` to apply changes at runtime without a full reload.
- Smart listener in `__init__.py`: applies threshold/debounce changes in real time; performs a full reload only when power sensors or managed devices change.
- New `reorder` step in `OptionsFlow`: allows drag-and-drop style reordering of managed devices via dropdown slots (`pos_0`, `pos_1`, …).
- "Reorder devices" toggle in the options form to access the new reorder step.
- IT/EN translations for the new `number` entities.
- Generic `invalid_input` error message in `strings.json`.
- README: added documentation on the `is_over_threshold` automation trigger and a new section on live threshold configuration via the dashboard.

### Fixed
- Options flow validation now shows the correct specific error for each field (sensors, threshold, debounce, devices) instead of the generic `invalid_input` message.

---

## [1.0.6] - 2026-02-18

### Added
- Images and initial translations added to the integration.
- Card (`avoidblackout-card.js`) updated and registered for HA frontend caching.
- `hacs.json` and `manifest.json` configured for HACS compatibility.
- Comprehensive `README.md` with setup and usage instructions for the card and blueprint.
- Blueprints moved to the correct location for HACS discovery.

---

## [1.0.0] - 2026-02-17

### Added
- Initial release of the AvoidBlackout integration.
- Power monitoring via configurable power sensor entities.
- Automatic load shedding when power exceeds the configured threshold.
- Configurable debounce time to avoid flapping.
- Test mode to simulate actions without actually turning off devices.
- Config flow and options flow for full UI-based setup.
- Status sensor (`sensor.avoidblackout_status`) with `is_over_threshold` attribute for automations.
- `reset_history` service to clear the history of turned-off devices.

---

[Unreleased]: https://github.com/davpirelli/avoidblackout/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/davpirelli/avoidblackout/compare/v1.0.6...v1.1.0
[1.0.6]: https://github.com/davpirelli/avoidblackout/compare/v1.0.0...v1.0.6
[1.0.0]: https://github.com/davpirelli/avoidblackout/releases/tag/v1.0.0
