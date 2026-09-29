# Store Readiness Audit — {App name} v{version}+{build}

**Date:** {YYYY-MM-DD} · **Scope:** {iOS / Android / Both} · **Commit/branch:** {if known}

## Verdict: {✅ READY | ⚠️ READY WITH WARNINGS | ❌ NOT READY — N blockers}

| Store | ✅ Pass | ❌ Fail | ⚠️ Warn | 🔍 Manual |
|---|---|---|---|---|
| App Store | | | | |
| Google Play | | | | |

## ❌ Blockers (fix before upload)

### {ID} — {Check title}
- **Guideline:** {e.g. Apple 5.1.1(v)}
- **Evidence:** `{path/file.dart:LINE}` — {what was found}
- **Fix:** {concrete steps}
```dart
// snippet if helpful
```

## ⚠️ Warnings
{Same format, shorter.}

## Full checklist — App Store

| ID | Check | Guideline | Status | Evidence | Fix |
|---|---|---|---|---|---|

## Full checklist — Google Play

| ID | Check | Policy | Status | Evidence | Fix |
|---|---|---|---|---|---|

## 🔍 Outside the code (App Store Connect / Play Console)
- [ ] Privacy labels / Data safety form match SDKs and data flows found: {list SDKs found}
- [ ] Demo account + review notes (state the app's differentiator for 4.3)
- [ ] Age rating / content rating questionnaires
- [ ] Screenshots from the real build
- [ ] Privacy policy + support URLs live
- [ ] IAP products ready and attached (if any)
- [ ] {store-specific items from references}

## Not applicable
{IDs and one-line reason, e.g. "GEN-020 Restore purchases — no IAP"}

---
_Automated pre-submission check by store-readiness-audit. Not affiliated with Apple or Google. A clean report reduces rejection risk but does not guarantee approval — the stores' current guidelines are the final authority._
