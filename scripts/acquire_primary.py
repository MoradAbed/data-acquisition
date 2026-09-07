#!/usr/bin/env python3
"""P12B primary-source acquisition, run on a GitHub-hosted runner.

Fails hard, by design.  A silent partial success is worse than a red build,
because a partial success becomes a research panel.

Guarantees:
  * bytes are hashed BEFORE any parsing or decoding;
  * an existing artifact is NEVER overwritten -- differing bytes are stored
    alongside and linked by `supersedes`, because a changed source is data,
    not a bug (Phase 12B section H);
  * the ORIGINATING source stays marked PRIMARY; GitHub is recorded only as
    the transport and archive layer, never as the data source.

Usage:
  python3 scripts/acquire_primary.py --target usda_poc
  python3 scripts/acquire_primary.py --manifest targets.json --all
"""
import argparse, datetime, hashlib, json, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
PROV = os.path.join(ROOT, "provenance")
HASHES = os.path.join(ROOT, "hashes")
PARSER_VERSION = "P12B-acquire-1.0.0"

UA = ("p12b-acquisition-bridge/1.0 (systematic-trading research; "
      "public-domain government data; contact via repository issues)")


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def die(msg, code=1):
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(code)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})
    except Exception as e:
        return 0, b"", {"_error": str(e)}


def acquire(t):
    """t: one target dict from targets.json"""
    sid = t["source_id"]
    url = t["official_source_url"]
    print(f"--- {sid}\n    {url}")

    status, body, headers = fetch(url)

    # ---- fail-hard gate 1: HTTP status --------------------------------
    expect = t.get("expected_status", 200)
    if status != expect:
        die(f"{sid}: HTTP {status}, expected {expect}. "
            f"{headers.get('_error','')}")

    # ---- fail-hard gate 2: zero-byte ----------------------------------
    if not body:
        die(f"{sid}: zero-byte response from a 200 status -- refusing to "
            "record an empty artifact")

    # ---- hash BEFORE parsing ------------------------------------------
    digest = sha256_bytes(body)
    if len(digest) != 64:
        die(f"{sid}: hash could not be calculated")
    nbytes = len(body)

    # ---- fail-hard gate 3: minimum plausible size ---------------------
    minb = t.get("min_bytes", 1)
    if nbytes < minb:
        die(f"{sid}: {nbytes} bytes is below the declared minimum {minb} -- "
            "this usually means an error page was served with status 200")

    os.makedirs(RAW, exist_ok=True)
    os.makedirs(PROV, exist_ok=True)
    os.makedirs(HASHES, exist_ok=True)

    ext = t.get("extension") or os.path.splitext(url.split("?")[0])[1] or ".bin"
    fname = f"{sid}.{digest[:16]}{ext}"
    path = os.path.join(RAW, fname)

    # ---- immutability: never overwrite --------------------------------
    supersedes = None
    existing = sorted(f for f in os.listdir(RAW) if f.startswith(sid + "."))
    same = [f for f in existing if f == fname]
    diff = [f for f in existing if f != fname]
    if diff:
        # A differing retrieval of the same source. Retain BOTH.
        prior = os.path.join(RAW, diff[-1])
        supersedes = sha256_file(prior)
        print(f"    NOTE: source bytes differ from a previous acquisition\n"
              f"          previous {supersedes[:16]}  ({diff[-1]})\n"
              f"          current  {digest[:16]}\n"
              f"          BOTH retained; investigate why the source changed.")
    if same:
        print(f"    already acquired, byte-identical ({digest[:16]}); "
              "no write performed")
    else:
        with open(path, "wb") as f:
            f.write(body)
        if sha256_file(path) != digest:
            die(f"{sid}: write-back hash mismatch -- disk corruption")

    # ---- fail-hard gate 4: required provenance fields ------------------
    required = ["source_id", "dataset_id", "provenance_class",
                "official_source_name", "official_source_url"]
    missing = [k for k in required if not t.get(k)]
    if missing:
        die(f"{sid}: provenance incomplete, missing {missing}")
    if t["provenance_class"] != "primary":
        die(f"{sid}: provenance_class is {t['provenance_class']!r}; this "
            "workflow acquires primary sources only")

    rec = {
        "acq_version": "ACQ-1",
        "source_id": sid,
        "dataset_id": t["dataset_id"],
        "provenance_class": "primary",
        "official_source_name": t["official_source_name"],
        "official_source_url": url,
        "transport_and_archive_layer": {
            "note": "GitHub is transport and archive only, NOT the data source",
            "repository": os.environ.get("GITHUB_REPOSITORY", "<local>"),
            "commit": os.environ.get("GITHUB_SHA", "<pending>"),
            "run_id": os.environ.get("GITHUB_RUN_ID", "<local>"),
            "runner": os.environ.get("RUNNER_OS", "<local>"),
        },
        "request": {"url": url, "method": "GET",
                    "headers_sent": {"User-Agent": UA}},
        "acquisition_channel": "github_actions_runner",
        "acquisition_timestamp_utc": now(),
        "http_status": status,
        "content_type": headers.get("Content-Type", ""),
        "content_length_header": headers.get("Content-Length", ""),
        "content_bytes": nbytes,
        "content_sha256": digest,
        "stored_path": os.path.relpath(path, ROOT),
        "release": {
            "reference_date": t.get("reference_date"),
            "source_publication_date": t.get("source_publication_date"),
            "source_publication_time": t.get("source_publication_time"),
            "timezone": t.get("timezone"),
            "publication_time_evidence": t.get("publication_time_evidence",
                                               "NOT ESTABLISHED FROM ARTIFACT"),
        },
        "usable_from_utc": None,
        "parser": {"script": "scripts/acquire_primary.py",
                   "script_sha256": sha256_file(os.path.abspath(__file__)),
                   "version": PARSER_VERSION},
        "observations": [],
        "supersedes": supersedes,
    }
    with open(os.path.join(PROV, f"{sid}.json"), "w") as f:
        json.dump(rec, f, indent=2)
    with open(os.path.join(HASHES, f"{sid}.sha256"), "w") as f:
        f.write(f"{digest}  {os.path.relpath(path, ROOT)}\n")
    print(f"    OK  {nbytes} bytes  sha256 {digest}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(ROOT, "targets.json"))
    ap.add_argument("--target")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    targets = json.load(open(a.manifest))["targets"]
    if a.target:
        targets = [t for t in targets if t["source_id"] == a.target] or die(
            f"no target named {a.target}")
    elif not a.all:
        die("specify --target <id> or --all")
    recs = [acquire(t) for t in targets]
    print(f"\n{len(recs)} artifact(s) acquired from primary sources.")


if __name__ == "__main__":
    main()
