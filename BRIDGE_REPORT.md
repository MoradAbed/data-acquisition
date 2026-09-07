# P12B ACQUISITION BRIDGE — STATUS AND OPERATING INSTRUCTIONS

## What this repository is

The transport and archive layer for primary-source inventory data used by a
systematic-trading research programme. **It is not a data source.** Every
artifact here originates from EIA or USDA and is labelled `provenance_class:
primary` with the official URL recorded. GitHub is the courier and the
immutable archive, nothing more.

## Why it exists

The research environment cannot reach `eia.gov`, `usda.gov` or
`esmis.nal.usda.gov` — every request returns HTTP 000 through a blocking
proxy. The same block applies on the researcher's own machine. GitHub-hosted
Actions runners have open egress, so a runner fetches the official file,
hashes the raw bytes before parsing anything, and commits the artifact. The
research environment then pulls it through `raw.githubusercontent.com` and
recomputes the hash independently.

```
OFFICIAL PRIMARY SOURCE → GITHUB RUNNER → RAW BYTES → SHA-256
  → IMMUTABLE COMMIT → raw.githubusercontent.com → LOCAL HASH VERIFY
```

## Current status

| Link | Status |
|---|---|
| 1. Primary source reachable from a runner | **UNPROVEN** — no run has executed |
| 2. Raw bytes preserved | Implemented, untested against a primary source |
| 3. SHA-256 before parsing | Implemented and unit-tested |
| 4. Committed to durable history | Implemented, untested |
| 5. Retrievable via raw.githubusercontent | **PROVEN** |
| 6. Local hash equals recorded hash | **PROVEN** |
| 7. Verifier detects a mismatch | **PROVEN** |

Links 5–7 were proven against a control on a reachable public repository.
Links 1–4 require one authenticated `git push` of this repository, which the
research session could not perform — its GitHub token authenticates but has no
repository bound, and neither the container nor the desktop VM holds git
credentials.

## To run it

```bash
git add -A && git commit -m "P12B bridge" && git push
```
Then in GitHub: **Actions → "P12B primary-source acquisition POC" → Run
workflow → target: `all`**.

Step 3 of the workflow prints reachability from the runner. **If EIA and USDA
do not return 200 there, stop — the bridge concept is dead and no amount of
further engineering helps.**

If the run succeeds, download the `p12b-provenance` artifact and verify from
the research environment:

```bash
python3 verify_roundtrip.py \
  --repo MoradAbed/data-acquisition \
  --commit <commit printed by workflow step 8> \
  --provenance-dir ./provenance
```

Exit 0 means byte-for-byte equality from the official source to the research
environment. Anything else is a failure and must not be worked around.

## Rules this code enforces, not merely documents

- **Hash before parse.** Bytes are hashed on arrival; nothing is decoded first.
- **Never overwrite.** A re-acquisition producing different bytes stores the
  new artifact alongside the old and records `supersedes`. A source that
  changed is data, not a bug — investigate, do not silently take the newer one.
- **Primary only.** `acquire_primary.py` refuses any target whose
  `provenance_class` is not `primary`. A third-party mirror cannot enter
  through this path even by accident.
- **Fail hard.** Wrong HTTP status, zero bytes, a body below the declared
  minimum size (the usual signature of an error page served with status 200),
  an uncomputable hash, missing provenance, or an in-place modification of
  `raw/` all fail the build.
- **No secrets.** Only `contents: write` is granted. All targets are
  public-domain government files and no credential is used or stored.

## Release timing

`source_publication_time` is deliberately left `null` until it is established
from the artifact itself or an official release calendar. The 12:00 ET WASDE
and 10:30 ET WPSR conventions are **not** to be assumed from memory or general
documentation. Until a real timestamp is captured, `usable_from_utc` stays
`null` and no observation is admissible for research.

## Layout

```
.github/workflows/p12b_poc.yml   the workflow
scripts/acquire_primary.py       runner-side fetch, hash, provenance
targets.json                     the primary-source targets
POC_DATES.json                   POC dates, fixed before any retrieval
raw/                             immutable artifacts, never overwritten
provenance/                      one ACQ-1 record per artifact
hashes/                          sha256 sidecars
verification/                    round-trip results
```
