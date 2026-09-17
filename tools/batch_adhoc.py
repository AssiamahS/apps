#!/usr/bin/env python3
"""Clone each repo, auto-detect its xcodegen layout, add the ad hoc lane, push, enable Pages."""
import os, sys, glob, json, subprocess, yaml

BASE = os.path.expanduser("~/adhoc-batch")
PATCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "add_adhoc_lane.py")  # ~/apps-hub/tools
# repo -> ASC title
REPOS = {
    "stairmatcher": "StairMatch", "lastlegjet": "Last Leg Jet", "instaFollowUp": "InstaFollowUp", "AIagent": "A.I.agents",
    "steppes": "Steppes", "sylvestere": "Sylvestere", "djsly_web": "DJ5ly", "auroraOS": "Aurora", "topmanios": "topmanOS",
    "otterOS": "Otto", "lyrixyz": "lyrixyz", "reminda": "remindas", "carplayAI": "carplayAI", "carplayMAPS": "carplaymaps",
    "carplay": "carplayOS", "shares": "sharesOS", "ConyOS": "ConyOS", "leetcodeOS": "leetcodeOS", "alexa": "slyalarms",
    "cryptoOS": "cryptoOS", "scipioapp": "scipioOS", "music": "djSly", "pmOS": "PMiOS", "amapiano-ios": "amapiano",
    "partyrock": "PartyHop", "mindchuk": "MindChuk",
}
only = sys.argv[1:]
os.makedirs(BASE, exist_ok=True)

def sh(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()

results = {}
for repo, title in REPOS.items():
    if only and repo not in only: continue
    try:
        d = os.path.join(BASE, repo)
        if not os.path.isdir(d):
            sh(f"git clone -q git@github.com:AssiamahS/{repo}.git {d}")
        else:
            sh("git fetch -q && git reset -q --hard origin/HEAD", cwd=d)
        pyml = "project.yml" if os.path.exists(f"{d}/project.yml") else "ios/project.yml"
        root = os.path.dirname(pyml) or "."
        y = yaml.safe_load(open(f"{d}/{pyml}"))
        project = y["name"]
        targets = y.get("targets", {})
        app = next((n for n, t in targets.items() if t.get("type") == "application" and t.get("platform") == "iOS"), None)
        if not app: raise RuntimeError("no iOS application target")
        st = targets[app].get("settings", {}) or {}
        bundle = (st.get("base") or {}).get("PRODUCT_BUNDLE_IDENTIFIER") or st.get("PRODUCT_BUNDLE_IDENTIFIER")
        if not bundle:
            import re
            m = re.search(r"PRODUCT_BUNDLE_IDENTIFIER:\s*([\w.\-]+)", open(f"{d}/{pyml}").read()); bundle = m.group(1) if m else None
        if not bundle: raise RuntimeError("no bundle id")
        scheme = next(iter(y.get("schemes", {app: 1}).keys()), app)
        watch = [dep["target"] for dep in targets[app].get("dependencies", []) if isinstance(dep, dict) and targets.get(dep.get("target"), {}).get("platform") == "watchOS"]
        # workflow with xcodebuild
        wfs = sorted(glob.glob(f"{d}/.github/workflows/*.yml"))
        wf = next((w for w in wfs if "xcodebuild" in open(w).read() and "pages" not in os.path.basename(w)), None)
        if not wf: raise RuntimeError("no xcodebuild workflow")
        # icon: main target's appiconset, largest png
        srcs = targets[app].get("sources", [])
        srcdirs = [s if isinstance(s, str) else s.get("path") for s in srcs]
        cands = []
        for sd in srcdirs:
            cands += glob.glob(f"{d}/{root}/{sd}/**/AppIcon.appiconset/*.png", recursive=True)
        if not cands: cands = glob.glob(f"{d}/**/AppIcon.appiconset/*.png", recursive=True)
        if not cands: raise RuntimeError("no app icon png")
        icon = max(cands, key=os.path.getsize)
        args = [sys.executable, PATCHER, d, os.path.relpath(wf, d), root, project, scheme, bundle, title, os.path.relpath(icon, d)] + (watch[:1])
        out = subprocess.run(args, capture_output=True, text=True)
        if out.returncode != 0: raise RuntimeError(out.stdout + out.stderr)
        PRE = {"djsly_web": '(cd "$GITHUB_WORKSPACE" && bash ios/bundle-web.sh)'}
        if repo in PRE:
            w = open(wf).read()
            w = w.replace("          xcodegen generate\n      - name: Archive (unsigned)", f"          {PRE[repo]}\n          xcodegen generate\n      - name: Archive (unsigned)", 1)
            open(wf, "w").write(w)
        sh('git add -A && git -c commit.gpgsign=false commit -q -m "ci: ad hoc IPA lane + GitHub Pages install page\n\nTestFlight installs are blocked by an Apple Account billing hold, so every\npush also exports a release-testing IPA for registered iPhones and commits\nit under web/ipa with an itms-services install page. Archive is unsigned\n(cloud-signed archives mint a dev cert per run and hit the 10-cert cap);\nexportArchive does the signing." && git push -q --no-verify origin HEAD', cwd=d)
        sh(f"gh api -X POST repos/AssiamahS/{repo}/pages -f build_type=workflow >/dev/null 2>&1 || true")
        results[repo] = f"ok  {project}/{scheme} {bundle} root={root} watch={watch[:1]} icon={os.path.basename(icon)}"
    except Exception as e:
        results[repo] = "ERR " + str(e).strip().splitlines()[-1][:160]
    print(f"{repo:<16} {results[repo]}", flush=True)
json.dump(results, open(os.path.join(BASE, "results.json"), "w"), indent=1)
