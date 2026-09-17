#!/usr/bin/env python3
"""Add the 'ad hoc IPA -> GitHub Pages install page' lane to an xcodegen iOS repo.

usage: add_adhoc_lane.py <repo_dir> <workflow_file> <root> <project> <scheme> <bundle_id> <title> <icon_png> [strip_dep_target]
"""
import os, re, sys, subprocess
from PIL import Image

repo, wf, root, project, scheme, bundle, title, icon = sys.argv[1:9]
strip = sys.argv[9] if len(sys.argv) > 9 else ""
slug = os.path.basename(os.path.abspath(repo))
site = os.environ.get("SITE") or f"https://assiamahs.github.io/{slug}"
os.chdir(repo)

# 1. export options
rootp = "" if root == "." else root.rstrip("/") + "/"
open(f"{rootp}ExportOptionsAdHoc.plist", "w").write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>method</key><string>release-testing</string>
	<key>teamID</key><string>QGMAWHX827</string>
	<key>signingStyle</key><string>automatic</string>
	<key>compileBitcode</key><false/>
	<key>thinning</key><string>&lt;none&gt;</string>
</dict>
</plist>
''')

# 2. web assets
os.makedirs("web/ipa", exist_ok=True)
im = Image.open(icon).convert("RGB")
im.resize((180, 180)).save("web/icon-180.png"); im.resize((512, 512)).save("web/icon-512.png")
open("web/install.html", "w").write(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Install {title}</title>
<link rel="apple-touch-icon" href="icon-180.png">
<style>body{{margin:0;background:#0d0f14;color:#fff;font:17px/1.55 -apple-system,BlinkMacSystemFont,system-ui,sans-serif}}main{{max-width:520px;margin:0 auto;padding:64px 22px}}
img{{width:96px;height:96px;border-radius:22px}}h1{{margin:18px 0 6px;letter-spacing:-.02em}}p{{color:#8c909a}}
.btn{{display:block;text-align:center;margin:28px 0 12px;padding:16px;border-radius:14px;background:#00c7c0;color:#000;font-weight:800;text-decoration:none;font-size:18px}}
ol{{color:#d4d4d4;padding-left:20px}}li{{margin:6px 0}}.meta{{font-size:13px;color:#5a5e68}}</style></head>
<body><main>
<img src="icon-180.png" alt=""><h1>Install {title}</h1>
<p>Direct install for registered iPhones. No App Store, no TestFlight.</p>
<a class="btn" href="itms-services://?action=download-manifest&amp;url={site}/ipa/manifest.plist">Install on this iPhone</a>
<ol><li>Open this page in <b>Safari</b> on the iPhone.</li><li>Tap Install, then <b>Install</b> on the iOS prompt.</li><li>It lands in the App Library (search for it if it's not on a Home Screen page).</li></ol>
<p class="meta">Build BUILD_NUMBER · BUILD_DATE · only installs on iPhones registered to the developer account.</p>
</main></body></html>
''')
if not os.path.exists("web/index.html"):
    open("web/index.html", "w").write(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=install.html"><title>{title}</title><a href="install.html">Install {title}</a>\n')
if os.environ.get("LEGACY_PAGES"):
    if os.path.exists(".github/workflows/pages.yml"): os.remove(".github/workflows/pages.yml")
elif not os.path.exists(".github/workflows/pages.yml"):
    open(".github/workflows/pages.yml", "w").write('''name: Pages

on:
  push:
    branches: [main]
    paths: ['web/**', '.github/workflows/pages.yml']
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web
      - id: deployment
        uses: actions/deploy-pages@v4
''')
gi = open(".gitignore").read() if os.path.exists(".gitignore") else ""
if "build/" not in gi:
    open(".gitignore", "a").write(f"\n{rootp}build/\n{rootp}*.xcodeproj\n")

# 3. workflow job
cd = ""
wd = f"        working-directory: {root}\n"
strip_line = (f"          sed -i '' '/^      - target: {strip}$/d' project.yml\n"
              f"          perl -0pi -e 's/^    dependencies:\\n(?!      - )//m' project.yml   # drop the key if it is now empty\n") if strip else ""
job = f'''
  adhoc:
    # Sideload lane: ad hoc IPA for registered iPhones, served from GitHub Pages via itms-services.
    # Exists because a billing hold on the Apple Account blocks every TestFlight install.
    # Archive is UNSIGNED on purpose: a cloud-signed archive mints a throwaway dev cert per run
    # and trips the 10-certificate cap; exportArchive does the real signing.
    name: Ad hoc IPA -> install page
    runs-on: macos-26
    timeout-minutes: 45
    if: github.event_name != 'pull_request'
    permissions:
      contents: write
      actions: write
    concurrency:
      group: adhoc-publish
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4
      - name: Write App Store Connect API key
        env:
          ASC_KEY_P8: ${{{{ secrets.ASC_KEY_P8 }}}}
          ASC_KEY_ID: ${{{{ secrets.ASC_KEY_ID }}}}
        run: |
          mkdir -p "$RUNNER_TEMP/asc" "$HOME/private_keys"
          printf '%s' "$ASC_KEY_P8" | base64 --decode > "$RUNNER_TEMP/asc/AuthKey.p8"
          cp "$RUNNER_TEMP/asc/AuthKey.p8" "$HOME/private_keys/AuthKey_${{ASC_KEY_ID}}.p8"
      - name: Install XcodeGen
        run: brew install xcodegen
      - name: Generate Xcode project (iPhone only)
{wd}        run: |
          {cd}sed -i '' "s/^    CURRENT_PROJECT_VERSION: .*/    CURRENT_PROJECT_VERSION: $GITHUB_RUN_NUMBER/" project.yml
{strip_line}          {cd}xcodegen generate
      - name: Archive (unsigned)
{wd}        run: |
          set -o pipefail
          {cd}xcodebuild archive \\
            -project {project}.xcodeproj \\
            -scheme {scheme} \\
            -configuration Release \\
            -destination 'generic/platform=iOS' \\
            -archivePath build/{project}.xcarchive \\
            CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \\
            CURRENT_PROJECT_VERSION=$GITHUB_RUN_NUMBER
      - name: Export ad hoc IPA (cloud signing)
{wd}        env:
          ASC_KEY_ID: ${{{{ secrets.ASC_KEY_ID }}}}
          ASC_ISSUER_ID: ${{{{ secrets.ASC_ISSUER_ID }}}}
        run: |
          set -o pipefail
          {cd}xcodebuild -exportArchive \\
            -archivePath build/{project}.xcarchive \\
            -exportOptionsPlist ExportOptionsAdHoc.plist \\
            -exportPath build/adhoc \\
            -allowProvisioningUpdates \\
            -authenticationKeyPath "$RUNNER_TEMP/asc/AuthKey.p8" \\
            -authenticationKeyID "$ASC_KEY_ID" \\
            -authenticationKeyIssuerID "$ASC_ISSUER_ID"
          ls -la build/adhoc
      - name: Publish install page to GitHub Pages
        working-directory: ${{{{ github.workspace }}}}
        env:
          GH_TOKEN: ${{{{ github.token }}}}
        run: |
          cd "$GITHUB_WORKSPACE"
          mkdir -p web/ipa
          cp {rootp}build/adhoc/*.ipa web/ipa/{project}.ipa
          VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' {rootp}build/{project}.xcarchive/Products/Applications/{project}.app/Info.plist)
          cat > web/ipa/manifest.plist <<EOF2
          <?xml version="1.0" encoding="UTF-8"?>
          <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
          <plist version="1.0"><dict><key>items</key><array><dict>
            <key>assets</key><array>
              <dict><key>kind</key><string>software-package</string><key>url</key><string>{site}/ipa/{project}.ipa</string></dict>
              <dict><key>kind</key><string>display-image</string><key>url</key><string>{site}/icon-180.png</string></dict>
              <dict><key>kind</key><string>full-size-image</string><key>url</key><string>{site}/icon-512.png</string></dict>
            </array>
            <key>metadata</key><dict>
              <key>bundle-identifier</key><string>{bundle}</string>
              <key>bundle-version</key><string>${{VERSION}}</string>
              <key>kind</key><string>software</string>
              <key>title</key><string>{title}</string>
            </dict>
          </dict></array></dict></plist>
          EOF2
          sed -i '' -E "s/Build [^·]*· [^·]*·/Build $GITHUB_RUN_NUMBER (v$VERSION) · $(date -u +%Y-%m-%d) ·/; s/BUILD_NUMBER/$GITHUB_RUN_NUMBER/; s/BUILD_DATE/$(date -u +%Y-%m-%d)/" web/install.html || true
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          # never rebase binaries: start from origin/main each attempt and re-copy our outputs
          for attempt in 1 2 3 4; do
            git fetch -q origin main
            git checkout -q -B main origin/main
            mkdir -p web/ipa
            cp {rootp}build/adhoc/*.ipa web/ipa/{project}.ipa
            git checkout -q origin/main -- web/install.html 2>/dev/null || true
            sed -i '' -E "s/Build [^·]*· [^·]*·/Build $GITHUB_RUN_NUMBER (v$VERSION) · $(date -u +%Y-%m-%d) ·/; s/BUILD_NUMBER/$GITHUB_RUN_NUMBER/; s/BUILD_DATE/$(date -u +%Y-%m-%d)/" web/install.html || true
            git add web/ipa web/install.html
            git commit -q -m "build: ad hoc IPA build $GITHUB_RUN_NUMBER" || exit 0
            git push -q origin HEAD:main && break
            echo "push rejected, retrying ($attempt)"; sleep $((attempt * 5))
          done
          {"true  # legacy Pages rebuilds on every push" if os.environ.get("LEGACY_PAGES") else "gh workflow run pages.yml --ref main"}
'''
s = open(wf).read()
if "\n  adhoc:" in s:
    s = s[:s.index("\n  adhoc:")]
    print("replacing existing adhoc job in", wf)
s = s.rstrip("\n") + "\n" + job
open(wf, "w").write(s)
print("adhoc job written to", wf)

# 4. make the existing TestFlight archive unsigned too (cert cap) — only where it is cloud-signed and no persistent dev cert
if "DEV_CERT_P12" not in s:
    pat = re.compile(r"(xcodebuild archive \\\n(?:.*\n)*?)            -allowProvisioningUpdates \\\n            -authenticationKeyPath \"\$RUNNER_TEMP/asc/AuthKey\.p8\" \\\n            -authenticationKeyID \"\$ASC_KEY_ID\" \\\n            -authenticationKeyIssuerID \"\$ASC_ISSUER_ID\" \\\n            CURRENT_PROJECT_VERSION=\$GITHUB_RUN_NUMBER")
    s2, n = pat.subn(r'\1            CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \\\n            CURRENT_PROJECT_VERSION=$GITHUB_RUN_NUMBER', s)
    if n:
        s2 = s2.replace("- name: Archive (cloud-managed signing)", "- name: Archive (unsigned; exportArchive cloud-signs)")
        open(wf, "w").write(s2); print(f"testflight archive switched to unsigned ({n})")
subprocess.run(["python3", "-c", f"import yaml; yaml.safe_load(open('{wf}')); print('yaml ok')"], check=True)
