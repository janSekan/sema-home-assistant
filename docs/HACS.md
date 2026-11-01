# HACS publication status

The repository contains one integration under `custom_components/sema` and a
root `hacs.json` for Core 2026.9.4+. Integration version: 0.1.0. This version is
independent of SEMA device firmware versions.

The default branch can be installed as a HACS custom repository. Version tags
(`v` plus the manifest version) trigger the release workflow. It runs all checks
before creating a full GitHub Release, verifies the version and publishes the
reviewable notes from docs/RELEASE_NOTES.md. Validation is read-only; only the
final publish job has contents-write permission. Before submitting to the default
HACS catalog, test HACS installation and upgrade. The owner selected the MIT license;
see [LICENSE](../LICENSE).
No catalog submission is made automatically.

Repository settings must include a description, searchable topics and enabled
Issues. Suggested description: Local read-only Home Assistant integration for
SEMA heat pump devices. Suggested topics: home-assistant, hacs,
custom-integration, heat-pump, sema.

The first HACS Action run accepted hacs.json, manifest and local brand assets,
but failed the description, topics and license checks. The owner explicitly
initially deferred all three. The owner subsequently selected MIT and updated
the repository's About fields. The workflow keeps all checks enabled; verify
the latest Actions result before submitting to the catalog.

The HACS workflow runs without ignored checks and without permission to post PR
comments. Its wrapper is pinned to a commit; the upstream HACS Docker image uses
the maintained `main` tag. Hassfest validates with the documented pinned Core
source. Validation jobs use read-only repository permissions.

Brand assets are included locally in `custom_components/sema/brand`.
Internal network addresses, deployment records and local development history
are intentionally excluded from this public repository. Public `main` was
prepared as a separate initial snapshot; local development history was retained.

References: [HACS requirements](https://hacs.xyz/docs/publish/start/),
[integrations](https://hacs.xyz/docs/publish/integration/) and
[catalog submission](https://hacs.xyz/docs/publish/include/).
