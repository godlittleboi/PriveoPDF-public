# Public source snapshot changelog

Changes relevant to the current source snapshot. Its exact source commit is
recorded in `PUBLIC_SOURCE_MANIFEST.json`; this is not an installable binary
release.

## Current source publication

- Updated the selected sources, including isolated PDF rendering and atomic
  publication of split outputs after successful processing.
- Applied Apache License 2.0 to PriveoPDF-owned code and documentation, with
  `NOTICE`. Earlier publications retain their original licenses; third-party
  components retain theirs.
- Updated public replacement modules to match the application interfaces while
  keeping private Git updates and internal beta history disabled.
- Included the Linux source launcher and aligned public installation guides,
  quality checks and English product description with the exported files.
- Retained Qt LGPL/GPL notices and the corresponding-source lock. Their exact
  versions are recorded in `uv.lock` and the third-party source inventory.
- Public Discussions accept questions, ideas and feedback. External code
  contributions and pull requests are not accepted. Potential vulnerabilities
  use the private reporting channel described in `SECURITY.md`.

No installable binary is published by this source export. Future features and
release dates are not promised.
