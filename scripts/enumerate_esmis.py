#!/usr/bin/env python3
"""Enumerate the USDA ESMIS WASDE publication index.

ESMIS file paths embed opaque Fedora identifiers that are NOT derivable from
the release date, e.g.

  /sites/default/release-files/3t945q76s/x920fx22m/ff365560t/wasde-05-10-2013.pdf
                                          ^^^^^^^^^ ^^^^^^^^^ not derivable

So the only way to reach a dated issue is to walk the publication index and
read the hrefs.  This builds a date -> {pdf,xls,txt} map and fails hard if any
required date is missing, because a silently absent vintage is exactly the
failure that would let a 23-of-24 result be reported as a pass.

Usage:
  python3 scripts/enumerate_esmis.py --pages 30 --require p12_3_sample.json
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error

PUB = "https://esmis.nal.usda.gov/concern/publications/3t945q76s"
UA = ("p12b-acquisition-bridge/1.0 (systematic-trading research; "
      "public-domain government data; contact via repository issues)")
# wasde-MM-DD-YYYY.ext  (pre-2017 naming) and wasdeMMYY.ext (later naming)
HREF = re.compile(
    r'href="([^"]*?/release-files/[^"]*?/(wasde-(\d{2})-(\d{2})-(\d{4})'
    r'|wasde(\d{2})(\d{2})[a-z0-9]*)\.(pdf|xls|xlsx|txt|xml))"', re.I)


def get(url, timeout=60, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < tries - 1:
                time.sleep(3 * (i + 1)); continue
            return e.code, ""
        except Exception:
            if i < tries - 1:
                time.sleep(3 * (i + 1)); continue
            return 0, ""
    return 0, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=30)
    ap.add_argument("--require", default="")
    ap.add_argument("--out", default="esmis_index.json")
    a = ap.parse_args()

    index, pages_ok = {}, 0
    for p in range(1, a.pages + 1):
        url = f"{PUB}?locale=en&page={p}"
        code, html = get(url)
        if code != 200 or not html:
            print(f"  page {p:>3}: HTTP {code} — skipped")
            continue
        pages_ok += 1
        found = 0
        for m in HREF.finditer(html):
            href, _, mm, dd, yyyy, mm2, yy2, ext = m.groups()
            if yyyy:
                date = f"{yyyy}-{mm}-{dd}"
            else:
                # wasdeMMYY -> day unknown from the filename alone; skip.
                # Only the explicit wasde-MM-DD-YYYY form is admissible here,
                # because a guessed day is a fabricated release date.
                continue
            if href.startswith("/"):
                href = "https://esmis.nal.usda.gov" + href
            index.setdefault(date, {})[ext.lower()] = href
            found += 1
        print(f"  page {p:>3}: {found:>3} file links, {len(index):>4} dates so far")

    if not index:
        print("::error::enumeration produced nothing — the index layout may have "
              "changed, or the host refused every page")
        return 1

    ds = sorted(index)
    print(f"\n{pages_ok} pages read, {len(index)} dated releases, "
          f"{ds[0]} .. {ds[-1]}")
    with open(a.out, "w") as f:
        json.dump({"source": PUB, "pages_read": pages_ok,
                   "n_dates": len(index), "index": index}, f, indent=2)

    if a.require:
        need = json.load(open(a.require))["selected"]
        missing = [d for d in need if d not in index]
        have = [d for d in need if d in index]
        print(f"\nrequired vintages: {len(have)} of {len(need)} located")
        for d in need:
            fmts = ",".join(sorted(index[d])) if d in index else "MISSING"
            print(f"   {d}  {fmts}")
        if missing:
            print(f"::error::{len(missing)} required vintage(s) not found in the "
                  f"index: {missing}. Increase --pages, or the index layout "
                  f"changed. Do NOT substitute other dates.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
