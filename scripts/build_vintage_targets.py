#!/usr/bin/env python3
"""Build the acquisition target list for the 24 seeded USDA vintages.

The sample is FIXED: p12_3_sample.json, seed 20260907, drawn blind in Phase
12A before any retrieval attempt.  It is not redrawn here and a date that
cannot be located is NOT substituted -- it is reported as missing and the run
fails, because a 23-of-24 result reported as a pass is exactly the failure the
acceptance criterion exists to prevent.

Prefers .xls over .pdf: the workbook carries table titles and unit headers as
cell values, so a parser can bind to a named table and its stated unit rather
than to a commodity name in flowing text.
"""
import argparse, json, sys

PREF = ["xls", "xlsx", "pdf", "txt"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="esmis_index.json")
    ap.add_argument("--sample", default="p12_3_sample.json")
    ap.add_argument("--out", default="targets_vintage.json")
    a = ap.parse_args()

    idx = json.load(open(a.index))["index"]
    smp = json.load(open(a.sample))
    dates = smp["selected"]
    print(f"sample: seed {smp['seed']}, {len(dates)} vintages, "
          f"rule: {smp['selection_rule'][:70]}...")

    targets, missing = [], []
    for d in dates:
        avail = idx.get(d, {})
        fmt = next((f for f in PREF if f in avail), None)
        if not fmt:
            missing.append(d); continue
        targets.append({
            "source_id": f"USDA-WASDE-{d}",
            "dataset_id": "INV-USDA-WASDE",
            "provenance_class": "primary",
            "official_source_name": f"USDA Office of the Chief Economist / ESMIS, WASDE {d}",
            "official_source_url": avail[fmt],
            "extension": f".{fmt}",
            "expected_status": 200,
            "min_bytes": 20000,
            "reference_date": d,
            "source_publication_date": d,
            "source_publication_time": None,
            "timezone": "America/New_York",
            "publication_time_evidence":
                "To be read from the artifact or the official release calendar; "
                "not assumed from general documentation.",
        })
    if missing:
        print(f"::error::{len(missing)} required vintage(s) absent from the "
              f"index: {missing}. Not substituting. Fix enumeration instead.")
        return 1
    json.dump({"_sample_seed": smp["seed"], "targets": targets},
              open(a.out, "w"), indent=2)
    fmts = {}
    for t in targets:
        fmts[t["extension"]] = fmts.get(t["extension"], 0) + 1
    print(f"{len(targets)} targets written to {a.out}  formats: {fmts}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
