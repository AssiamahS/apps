# Sideload lane tooling

- `add_adhoc_lane.py <repo> <workflow> <root> <project> <scheme> <bundle> <title> <icon> [watchTargetToStrip]`
  adds an `adhoc` CI job (unsigned archive → release-testing export → IPA + manifest committed to `web/ipa` → Pages dispatch),
  `web/install.html`, `pages.yml`, and switches a cloud-signed TestFlight archive to unsigned. Env: `SITE=` override, `LEGACY_PAGES=1`.
- `batch_adhoc.py [repo ...]` clones into `~/adhoc-batch`, auto-detects project.yml layout, runs the patcher, pushes, enables Pages.
- `adhoc_status.py` one line per repo: last run, adhoc job state, manifest live.

Why: an Apple Account billing hold blocks every TestFlight install; ad hoc profiles for the registered iPhone don't care.
Cert-cap trap: a cloud-signed `xcodebuild archive` mints a "Created via API" dev cert per run; 10 = "Choose a certificate to revoke".
