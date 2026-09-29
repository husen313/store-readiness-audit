# Changelog

## 1.0.1 — 2026-09-29

- Visual HTML report (`audit/report.html`): verdict banner, per-store scores, plain-language check cards with "why it matters" and copyable fixes, filters, clickable `file:line` links (VS Code / Cursor / Windsurf), and a tickable "outside the code" checklist. Works offline, light and dark mode.
- Plain-language titles and explanations for every check (`plain` and `why` fields in `report.json`)
- `--render` rebuilds `report.md` / `report.html` from an edited `report.json`, so the agent's verified corrections show up in the visual report
- Colored terminal verdict with the list of blockers
- Install for Cursor, Codex, Windsurf and Antigravity with `npx skills add`

## 1.0.0 — 2026-09-29

First public release.

- Scanner with ~35 checks across App Store, Google Play, and shared rules
- Rules verified against Apple's App Review Guidelines (Jun 2026 revision) and Google Play's API 36 target requirement (31 Aug 2026)
- False-pass protection: comment stripping, string-literal/`.arb` label matching, code + UI evidence for restore and account deletion, paywall-scoped legal links, merged-manifest permission checks, perceptual default-icon detection
- Regression test suite with "trap" and "clean" fixture projects
- Claude Code plugin + marketplace manifests; `.skill` build for the Claude app
