# Security policy

## Reporting a vulnerability

Please report vulnerabilities through a private GitHub security advisory. Do not
include unredacted secrets, private workshop files, or personal data in a public
issue.

## Data handling

Paradox Mod Workbench runs locally and does not upload scanned files. ZIP paths
are normalized before inspection; unsafe entries are reported and skipped.
Archive expansion is bounded by a configurable size limit.
