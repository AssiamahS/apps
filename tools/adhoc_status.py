#!/usr/bin/env python3
"""One line per repo: latest CI run, ad hoc job state, whether the install manifest is live."""
import json, subprocess, urllib.request, sys
REPOS = ["fitxapp","ottoOS","mindchuk","remotebontrol","stairmatcher","lastlegjet","instaFollowUp","AIagent","steppes","sylvestere",
         "djsly_web","auroraOS","topmanios","otterOS","lyrixyz","reminda","carplayAI","carplayMAPS","carplay","shares","ConyOS",
         "leetcodeOS","alexa","cryptoOS","scipioapp","music","pmOS","amapiano-ios","partyrock"]
def gh(*a):
    return subprocess.run(["gh",*a],capture_output=True,text=True).stdout
def live(repo):
    try:
        with urllib.request.urlopen(f"https://assiamahs.github.io/{repo}/ipa/manifest.plist",timeout=8) as r: return r.status==200
    except Exception: return False
rows=[]
for repo in REPOS:
    runs=json.loads(gh("run","list","-R",f"AssiamahS/{repo}","--limit","4","--json","databaseId,name,status,conclusion") or "[]")
    runs=[r for r in runs if r["name"]!="Pages"]
    adhoc="-"; run="-"
    if runs:
        run=f'{runs[0]["status"]}/{runs[0]["conclusion"]}'
        jobs=json.loads(gh("run","view",str(runs[0]["databaseId"]),"-R",f"AssiamahS/{repo}","--json","jobs") or "{}").get("jobs",[])
        for j in jobs:
            if j["name"].startswith("Ad hoc"):
                adhoc=j["conclusion"] or j["status"]
                if adhoc=="failure":
                    bad=[s["name"] for s in j["steps"] if s["conclusion"]=="failure"]
                    adhoc+=" @ "+(bad[0] if bad else "?")
    rows.append((repo,run,adhoc,live(repo)))
    print(f"{repo:<15} run={run:<22} adhoc={adhoc:<40} live={'YES' if rows[-1][3] else 'no'}",flush=True)
json.dump(rows,open("adhoc_status.json","w"))
print(f"\nlive: {sum(1 for r in rows if r[3])}/{len(rows)}")
