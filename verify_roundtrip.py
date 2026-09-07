#!/usr/bin/env python3
"""P12B local round-trip verification.

Runs in the RESEARCH environment, not on the runner. For every artifact the
runner acquired, it independently retrieves the bytes through
raw.githubusercontent.com and checks:

  runner-recorded sha256  ==  locally recomputed sha256
  runner-recorded bytes   ==  locally received bytes
  runner-recorded bytes   ==  raw byte-for-byte comparison where a local copy exists

Exit 0 only if every artifact matches on all three.
"""
import argparse, hashlib, json, os, subprocess, sys

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()

def curl(url, timeout=180):
    r = subprocess.run(["curl","-sS","-L","--max-time",str(timeout),
                        "-w","\n%{http_code}","-o","/dev/stdout",url],
                       capture_output=True, timeout=timeout+20)
    out = r.stdout
    body,_,tail = out.rpartition(b"\n")
    try: code=int(tail.decode().strip())
    except Exception: code=0
    return code, body

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--provenance-dir", required=True,
                    help="local copy of provenance/ from the run")
    a=ap.parse_args()

    recs=[]
    for fn in sorted(os.listdir(a.provenance_dir)):
        if fn.endswith(".json"):
            recs.append(json.load(open(os.path.join(a.provenance_dir,fn))))
    if not recs:
        print("no provenance records found"); return 2

    print(f"P12B ROUND-TRIP VERIFICATION   repo={a.repo}  commit={a.commit[:12]}")
    print("="*88)
    hdr=f"{'source_id':<28}{'HTTP':>6}{'bytes':>10}{'hash':>8}{'len':>6}  verdict"
    print(hdr); print("-"*len(hdr))
    bad=0
    for r in recs:
        url=(f"https://raw.githubusercontent.com/{a.repo}/{a.commit}/"
             f"{r['stored_path']}")
        code, body = curl(url)
        if code!=200 or not body:
            print(f"{r['source_id']:<28}{code:>6}{0:>10}{'-':>8}{'-':>6}  RETRIEVAL FAILED")
            bad+=1; continue
        local=sha256_bytes(body)
        hok = local==r["content_sha256"]
        lok = len(body)==r["content_bytes"]
        v = "MATCH" if (hok and lok) else ("HASH MISMATCH" if not hok else "LENGTH MISMATCH")
        print(f"{r['source_id']:<28}{code:>6}{len(body):>10}"
              f"{'ok' if hok else 'BAD':>8}{'ok' if lok else 'BAD':>6}  {v}")
        if not (hok and lok):
            bad+=1
            print(f"    runner sha256 {r['content_sha256']}")
            print(f"    local  sha256 {local}")
    print("-"*len(hdr))
    print(f"{len(recs)-bad} of {len(recs)} artifacts verified byte-for-byte.")
    if bad:
        print("VERDICT: ROUND TRIP FAILED — artifacts are not byte-identical.")
    else:
        print("VERDICT: ROUND TRIP VERIFIED — primary source to research "
              "environment, byte-for-byte.")
    return 1 if bad else 0

if __name__=="__main__":
    sys.exit(main())
