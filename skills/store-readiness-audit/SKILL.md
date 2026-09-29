---
name: store-readiness-audit
description: Audit a Flutter app's source code against Apple App Store Review Guidelines and Google Play policies BEFORE uploading, and produce a pass/fail checklist with evidence and fixes. Use this skill whenever the user wants to check, verify, audit, or review their app for App Store or Play Store submission, asks "is my app ready to upload/publish/submit", worries about app rejection, mentions review guidelines, Info.plist permission strings, privacy manifest, account deletion, Sign in with Apple, in-app purchase rules, target SDK, or wants a pre-release/pre-upload checklist — even if they don't say the word "audit".
license: MIT
compatibility: Flutter projects (iOS + Android). Needs Python 3.8+ and a code-execution environment; Pillow optional for icon checks.
---

# Store Readiness Audit

Check the current app code against App Store and Google Play requirements and list every check as PASS, FAIL, WARN, or MANUAL, with evidence (file + line) and a concrete fix. The goal is to catch rejections *before* upload, when fixing them is cheap.

## Status meanings

| Status | Meaning |
|---|---|
| ✅ PASS | Verified in code; meets the requirement |
| ❌ FAIL | Verified in code; will very likely cause rejection or an upload error. Blocker. |
| ⚠️ WARN | Risky or likely incomplete; could be rejected depending on how the app behaves |
| 🔍 MANUAL | Can't be decided from code alone; needs a human or a run of the app |

Never mark something PASS without evidence you actually saw. When unsure, use WARN or MANUAL — a false PASS is the worst outcome of this audit because it sends the user into review with a hidden problem.

## Workflow

### 1. Locate the project and scope
- Find the Flutter project root (the folder with `pubspec.yaml`). If the user uploaded a zip, extract it first.
- Decide scope: iOS, Android, or both. Default to **both** unless the user names one store.
- If there is no project in context, ask the user to upload it: run `flutter build appbundle --release` first, then zip the project without `.dart_tool/`, `Pods/`, and `build/` — **except keep `build/app/intermediates/merged_manifests/`**, which holds the final Android permissions after plugins merge theirs in. Without it, the permissions check can only say MANUAL.

### 2. Run the automated scanner
```bash
python3 <skill-dir>/scripts/scan_app.py <project-root> --store both --out <work-dir>/audit
```
`<skill-dir>` is this skill's folder (in Claude Code: `${CLAUDE_SKILL_DIR}`). Use `--store ios` or `--store android` to narrow. It writes `audit/report.json` and `audit/report.md` and prints a summary. The scanner covers deterministic checks: permission strings vs plugins, privacy manifest, bundle IDs, release signing, target SDK, dangerous permissions, cleartext traffic, restore purchases, account deletion signals, login options, ATT, export compliance, placeholder content, and more.

The scanner uses text heuristics, so treat its output as a strong first pass, not the final word. How it avoids false PASS results:
- Dart comments are stripped before matching, so `// TODO: restorePurchases()` never counts as evidence.
- Labels are matched inside string literals and `.arb` localization files; code identifiers like `reportError` or `privacyPolicyEnabled` don't count.
- Features that need both code and UI (restore purchases, account deletion) PASS only when the scanner finds the call **and** a visible label. Finding only one gives WARN.
- Paywall legal links are checked on the paywall screen itself, not anywhere in the app.
- Android permissions come from the merged release manifest; when it's missing or older than `pubspec.lock`, the result is MANUAL, never PASS.
- Default Flutter icons are detected by exact hash plus a perceptual fingerprint, so re-encoded or resized defaults are still caught.

### 3. Verify and deepen with code review
Read `references/apple_checks.md` and/or `references/google_play_checks.md` for the full check catalog. Then:

- **Confirm every FAIL** by opening the evidence file. Downgrade false positives (e.g., a "delete account" call that exists under a different name) and say why.
- **Resolve MANUAL/WARN items that code can answer.** Examples: trace the paywall widget to confirm a visible Restore button and links to Terms + Privacy Policy; trace the AI request path to confirm a consent dialog runs *before* personal data is sent; check that account deletion actually deletes server data, not just signs out.
- **Look for issues the scanner can't pattern-match**: hidden/debug menus reachable in release, features gated behind a server flag that reviewers can't reach, external purchase links for digital goods, login walls with no demo account, crashes on denied permissions (e.g., `image_picker` result not null-checked).

Cite `path/to/file.dart:LINE` for every finding you change or add.

### 4. Write the report
Use `assets/report_template.md` as the exact structure. Required parts:
1. **Verdict** — one line: `READY`, `READY WITH WARNINGS`, or `NOT READY (N blockers)`.
2. **Summary counts** per store.
3. **Blockers first** — every FAIL with fix steps and code snippets where helpful.
4. **Full checklist table** per store: ID, check, guideline, status, evidence, fix.
5. **Outside the code** — items that live in App Store Connect / Play Console (privacy labels, Data safety form, screenshots, review notes, demo account, age rating, content rating). Always include this section; many rejections come from metadata, not code.

Save the report as a Markdown file (e.g., `store-audit-<app>-<date>.md`) in the user's output location — the project root in Claude Code, or the outputs folder on claude.ai — and share it. Keep the chat reply short: verdict, blocker count, top 3 fixes.

### 5. Offer fixes
After the report, offer to apply the fixes (add missing Info.plist keys, create `PrivacyInfo.xcprivacy`, add a Restore button, fix release signing). Apply only what the user approves.

## Keeping rules current
Store rules change every year (Apple updated guidelines in Feb and Jun 2026; Google Play raises target API every August). Reference files carry a "last verified" date. If web search is available and that date is more than ~3 months old, search for recent App Review Guideline / Play policy changes and note anything new in the report. Apple: https://developer.apple.com/app-store/review/guidelines/ — Google: https://support.google.com/googleplay/android-developer/answer/11926878

## Notes on judgment
- Guideline 4.3 (spam / saturated categories) and 4.2 (minimum functionality) can't be proven from code. When the app is in a crowded category (fitness trackers, wallpapers, timers, flashlights, dating), mark MANUAL and suggest the user state the app's differentiator in App Review notes.
- The app's own purpose matters: a free app with no IAP skips payment checks (mark N/A, not PASS).
- Don't pad the report. Skip checks that don't apply, and list them once under "Not applicable".
