First public testing release of the SEMA Home Assistant integration.

### Features

- Local read-only device API v1, with Slovak and English setup and entity labels.
- Shared async polling, reauthentication, reconfiguration and mDNS discovery.
- Temperatures, percentage output, operating states and separate connection/freshness diagnostics.
- API revision 2 modes, configuration, heating curve and setback schedule: up to 49 entities, 25 enabled by default.
- Local SEMA brand images and filtered diagnostics. MIT licensed.

### Requirements and limits

- Home Assistant Core 2026.9.4 or newer; tested on 2026.9.4.
- A SEMA device with dedicated API v1 and its own HA read token.
- Extended entities require API v1 revision 2, tested with device firmware 1.3.0-testing.2.
- Installing this integration does not update device firmware. Older API v1 devices expose fewer entities.
- No pump control, electrical power/energy totals or COP calculation.

### Install or migrate from a manual installation

Add `https://github.com/janSekan/sema-home-assistant` to HACS custom repositories as an Integration, download this release and restart HA.

For an existing manual installation, back up the component directory first and keep the existing SEMA config entry. Do not delete the device or its entities: HACS replaces component files while pairing, token and entity registry stay in HA configuration. Verify the original entities after restart; HACS migration is awaiting user UI confirmation.

See the repository README and Slovak user guide for configuration, optional entities and troubleshooting. This release does not mean inclusion in the default HACS catalog or Home Assistant Core.
