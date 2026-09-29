# Changelog

## 1.0.0 — 2026-09-29

First public release.

- Scanner with ~35 checks across App Store, Google Play, and shared rules
- Rules verified against Apple's App Review Guidelines (Jun 2026 revision) and Google Play's API 36 target requirement (31 Aug 2026)
- False-pass protection: comment stripping, string-literal/`.arb` label matching, code + UI evidence for restore and account deletion, paywall-scoped legal links, merged-manifest permission checks, perceptual default-icon detection
- Regression test suite with "trap" and "clean" fixture projects
- Claude Code plugin + marketplace manifests; `.skill` build for the Claude app
