# HACS publication status

The repository contains one integration under `custom_components/sema` and a
root `hacs.json` for Core 2026.9.4+. Integration version: 0.1.0. This version is
independent of SEMA device firmware versions.

The default branch can be installed as a HACS custom repository. A GitHub Release
has not been published by the metadata push. Before submitting to the default
HACS catalog, verify successful HACS and hassfest runs, test HACS installation
and upgrade, publish a full GitHub Release and complete the owner's license decision.
No catalog submission is made automatically.

Repository settings must include a description, searchable topics and enabled
Issues. Suggested description: Local read-only Home Assistant integration for
SEMA heat pump devices. Suggested topics: home-assistant, hacs,
custom-integration, heat-pump, sema.

The HACS workflow runs without ignored checks and without permission to post PR
comments. Its wrapper is pinned to a commit; the upstream HACS Docker image uses
the maintained `main` tag. Hassfest validates with the documented pinned Core
source. All workflows use read-only repository permissions.

Brand assets are included locally in `custom_components/sema/brand`.
Internal network addresses, deployment records and local development history
are intentionally excluded from this public repository. Public `main` was
prepared as a separate initial snapshot; local development history was retained.

References: [HACS requirements](https://hacs.xyz/docs/publish/start/),
[integrations](https://hacs.xyz/docs/publish/integration/) and
[catalog submission](https://hacs.xyz/docs/publish/include/).
