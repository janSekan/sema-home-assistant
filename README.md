# SEMA for Home Assistant

Local, read-only Home Assistant integration for SEMA heat pump devices.
SEMA and Home Assistant communicate directly on your LAN; the portal is not
needed for regular updates. This is an early testing version, not a Home Assistant
Core integration and not yet listed in the default HACS catalog.

## Compatibility

| Component | Requirement |
| --- | --- |
| Home Assistant | Core 2026.9.4 or newer; tested on 2026.9.4 |
| SEMA | Dedicated device API v1 and a Home Assistant read token |
| Extended modes and settings | API v1 revision 2, tested with device firmware 1.3.0-testing.2 |

Older API v1 firmware exposes the original set of entities. Firmware without
the dedicated API cannot connect. Installing this integration does not update
SEMA firmware; contact your SEMA maintainer for a compatible device version.

## Install with HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/janSekan/sema-home-assistant`, type **Integration**.
3. Find **SEMA** and download it.
4. Restart Home Assistant.
5. On SEMA, open **Device information → Home Assistant** as an administrator,
   generate a dedicated token and copy it.
6. In **Settings → Devices & services**, configure the discovered SEMA device,
   or choose **Add integration → SEMA** and enter its full local HTTP(S) URL
   and the token.

Network discovery requires mDNS between SEMA and Home Assistant. Manual setup
remains available. HTTP does not encrypt the token; use it only on a trusted LAN.
Do not share tokens in screenshots, logs or issue reports.

For manual installation, copy the complete `custom_components/sema` directory
(including `brand` and `translations`) into your HA `config/custom_components`,
then restart HA and follow steps 5–6 above.

## What it provides

- Temperatures, power percentage and heating/DHW/defrost/fault states.
- Configured power, heating/cooling and summer/winter modes, reported operating
  state, heat source, DHW state, setback and tariff status.
- Heating reference temperature, optional read-only settings and six heating
  curve points, plus a weekly setback schedule summary.
- Separate connection and freshness diagnostics, and a privacy-filtered
  diagnostics download.

Full revision 2 capabilities create **49 entities**, with **25 enabled by default**.
Service settings, curve points, schedule and optional temperatures can be enabled
from the device's entity settings. Capabilities determine which entities exist.

All entities share one async coordinator: normally one state request every 30 s.
Device configuration is collected separately every 5 minutes and expires after
15 minutes. Unknown or stale data is not replaced with zero/off. No control
commands, watts, energy totals or COP calculations are exposed.

## Updates, removal and troubleshooting

Update through HACS and restart HA. After a firmware update adds capabilities,
reload the SEMA integration to discover new entities. Existing entity identities
use a persistent device UID, independent of its IP address.

For a changed address/token, use **Reconfigure**; a blank token preserves the
current one. Invalid/revoked tokens trigger reauthentication. To remove access,
revoke the token on SEMA and remove the SEMA config entry in HA. Removing it only
from HA does not revoke the device token.

If SEMA is reachable but the pump is unavailable, check the pump connection.
For failures, use the [issue tracker](https://github.com/janSekan/sema-home-assistant/issues),
include HA/firmware versions and a filtered diagnostics export, never credentials.

## Documentation and development

- [Slovenský používateľský návod](docs/USER_GUIDE.sk.md)
- [Entities](docs/ENTITIES.md), [discovery](docs/DISCOVERY.md), [diagnostics](docs/DIAGNOSTICS.md)
- [API v1](docs/API_PROPOSAL.md), [revision 2](docs/API_EXTENSIONS.md)
- [Development](docs/DEVELOPMENT.md), [validation](docs/VALIDATION.md), [branding](docs/BRANDING.md)
- [HACS publication status](docs/HACS.md)

Tests use synthetic fixtures and a loopback simulator, not customer credentials:

```bash
python3 tools/check_project.py
python3 -m unittest discover -s tests -v
python3 tools/mock_device.py --extended
```

HA-native tests target Core 2026.9.4; see the development guide for dependencies.
Fixtures and the public demo token are deliberately fictional.

## License

This integration is distributed under the [MIT License](LICENSE).
Copyright (c) 2026 janSekan.
