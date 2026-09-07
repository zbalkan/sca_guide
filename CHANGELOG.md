# Changelog

Notable user-facing changes are recorded here. Routine refactoring and test-only changes do not need an entry.

## 0.2.0

- Added a distinct **Not Applicable** review state for checks that do not apply to the target system or role.
- Split exported removal records into accepted-risk exceptions and not-applicable checks while keeping the existing export filenames.
- Added baseline compliance mappings to removed-check YAML records and Markdown reports.
- Tightened Wazuh SCA validation for requirement conditions and variable names/values.
- Fixed draft/baseline expiry so active drafts keep their uploaded baseline and expired review data is cleaned as one lifecycle unit.
- Added versioned draft persistence with strict recovery normalization and clearer handling of corrupt draft state.
- Preserved HTTP 413 responses for oversized uploads instead of converting them to generic upload failures.

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
