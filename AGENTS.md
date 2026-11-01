# SEMA Home Assistant contributor instructions

Communicate in Slovak with the maintainer. Read README.md, docs/DEVELOPMENT.md,
docs/API_PROPOSAL.md and docs/API_EXTENSIONS.md before changing integration code.
Check git status and preserve existing work. Do not force push or discard history.

The integration is read-only. Use one async coordinator and the dedicated HA
device API token. Never add pump control or bypass authentication as part of
sensor work. Unknown values stay unknown; distinguish connection, pump and data
freshness. Percentages are not watts or energy. Preserve persistent UID identity.

Run the relevant mock/HA-native tests and validation documented in
docs/VALIDATION.md. Do not contact or deploy to live customer devices without
authorization. Publishing a commit is separate from firmware/HA deployment.

Never publish tokens, HA configuration/.storage, databases, SSH keys, internal
network addresses, deployment backups or personal data. Fixtures are synthetic.
Keep diagnostic exports allowlisted and free of raw settings or schedules.

The owner explicitly selected the MIT license; preserve LICENSE and its notices.
HACS metadata publication is not admission to HACS defaults or HA Core.
