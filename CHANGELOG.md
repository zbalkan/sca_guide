# Changelog

Notable user-facing changes are recorded here. Routine refactoring and test-only changes do not need an entry.

## 0.2.0

- Added a distinct **Not Applicable** review state for controls that do not apply to the target platform or role.
- Changed the exception-record format to separate accepted-risk exceptions from not-applicable checks.
- Added baseline compliance mappings to removed-check records and to the Markdown export.

## 0.1.1

- Added ZIP digest validation during upload.

## 0.1.0

First public alpha release.

- Added a local browser-based workflow for tailoring Wazuh SCA policies.
- Added accepted, exception, and unreviewed review states with justified exceptions.
- Added draft recovery and local cleanup of temporary application data.
- Added tailored policy export with YAML and Markdown exception records.
- Added cross-platform packaging, CI, and manual PyPI Trusted Publishing.
- Established Python 3.11 as the minimum supported Python version, with Python 3.11 through 3.13 tested in CI.
- Established `pipx` and the `wazuhscatune` command as the supported installation and execution interface; the internal `sca` package is not a public library API.
