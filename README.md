# Store Readiness Audit

**Catch App Store and Google Play rejections before you upload.**

A Claude skill that audits your Flutter app's code against Apple's App Store Review Guidelines and Google Play policies. Every check comes back as ✅ PASS, ❌ FAIL, ⚠️ WARN, or 🔍 MANUAL, with `file:line` evidence and a concrete fix.

```
You:    Check my app before I upload to the stores.
Claude: ❌ NOT READY — 4 blockers
        1. GEN-020  No "Restore Purchases" on the paywall (Apple 3.1.1)
        2. AND-003  Release build is signed with the debug key
        3. IOS-020  Google Sign-In without Sign in with Apple (Apple 4.8)
        4. AND-002  targetSdk 35 — Play requires 36 since 31 Aug 2026
        Full report: store-audit-myapp-2026-09-29.md
```

See a [sample scanner output](docs/sample-report.md).

## What it checks

| Area        | App Store                                                                                                   | Google Play                                                                             |
| ----------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Build       | Bundle ID, 1024 icon (no alpha), default Flutter icon, export compliance, privacy manifest, Firebase config | applicationId,**targetSdk ≥ 36**, debug-signed release, debuggable, default icon |
| Permissions | Purpose strings for every plugin you use (missing or vague)                                                 | Restricted permissions (incl. ones plugins add), Photo & Video policy, AD_ID            |
| Accounts    | Sign in with Apple (4.8), in-app account deletion (5.1.1v), demo account                                    | Account deletion                                                                        |
| Payments    | Restore Purchases, Terms/EULA + Privacy on the paywall (3.1.2), external payment SDKs                       | Play Billing                                                                            |
| AI features | Consent before sending data to third-party AI (5.1.2i), report button, hardcoded API keys                   | AI-generated content reporting                                                          |
| Quality     | Placeholder text, debug URLs/banners, WebView-only apps (4.2), background modes, ATS                        | Cleartext traffic                                                                       |

The report also lists what code can't prove, such as privacy labels, Data safety, screenshots, age ratings, and closed-testing requirements, so nothing gets forgotten.

## How it works

1. **Scanner** (`scripts/scan_app.py`, pure Python) runs ~35 deterministic checks on the project.
2. **Claude verifies** each finding in your code and traces flows a script can't judge: whether the Restore button is actually visible, whether AI consent runs before the first request, whether account deletion removes server data.
3. **Report**: a verdict, blockers first, full checklists per store, and an "outside the code" list. Claude then offers to apply the fixes.

### Built to avoid false passes

A false ✅ sends you into review with a hidden problem, so the scanner is deliberately strict:

- Dart comments are stripped before matching, so `// TODO: restorePurchases()` never counts as evidence.
- Labels are matched only in string literals and `.arb` files. Identifiers like `reportError()` or `privacyPolicyEnabled` don't count.
- Restore purchases and account deletion PASS only when both the code call **and** a visible label are found.
- Paywall legal links are checked on the paywall screen, not anywhere in the app.
- Android permissions are read from the **merged release manifest**. If it's missing or stale, the result is MANUAL, never PASS.
- Default Flutter icons are detected by exact hash plus a perceptual fingerprint, so resized defaults are still caught.

## Install

### Claude Code (plugin)

```
/plugin marketplace add husen313/store-readiness-audit
/plugin install store-readiness-audit@store-readiness-audit
```

### Cursor, Codex, Windsurf, Antigravity (and other agents)

One command, using the open [skills](https://skills.sh) CLI:

```bash
npx skills add husen313/store-readiness-audit
```

It detects which agents you have and installs the skill into each one's skills folder. To pick agents or install for all projects:

```bash
npx skills add husen313/store-readiness-audit --agent cursor codex windsurf antigravity
npx skills add husen313/store-readiness-audit -g   # global
```

### Claude app (claude.ai, desktop, mobile)

Download `store-readiness-audit.skill` from [Releases](../../releases), then upload it in Claude's skills settings.

### Manual

Copy `skills/store-readiness-audit/` into your project's `.claude/skills/` folder, or into `~/.claude/skills/` for all your projects.

## Usage

In Claude Code, open your Flutter project and ask:

> Is my app ready for the App Store and Play Store?

In the Claude app, first build the release bundle so the final Android permissions exist:

```bash
flutter build appbundle --release
```

Then zip your project, leaving out `.dart_tool/`, `Pods/`, and `build/` (**but keep** `build/app/intermediates/merged_manifests/`). Upload the zip and ask the same question.

Run only the scanner:

```bash
python3 skills/store-readiness-audit/scripts/scan_app.py path/to/app --store both --out audit
```

Requirements: Python 3.8+. [Pillow](https://pypi.org/project/pillow/) is optional and enables the icon checks.

## Keeping rules current

Store rules change every year: Apple revised its guidelines twice in 2026, and Google raises the target API every August. Each reference file carries a "last verified" date, and the skill tells Claude to search for newer changes when that date is more than ~3 months old.

Rules last verified: **29 Sep 2026**. PRs that update rules are very welcome. Please cite the official source.

## Development

```bash
python3 tests/run_tests.py      # regression tests: "trap" and "clean" fixtures
bash tools/package_skill.sh     # builds dist/store-readiness-audit.skill
```

CI runs the tests on every push. Pushing a tag like `v1.0.1` publishes a release with the `.skill` file attached.

When adding a check:

1. Add it to `scan_app.py` with a stable ID.
2. Document it in `references/`.
3. Add expected results to both fixtures in `tests/run_tests.py`. If a naive version of the check could false-PASS, add that case to the trap project.

## Limitations

- Pattern-based scanning of Dart source. Unusual architectures, such as code generation or strings loaded from a server, can hide things, which is why Claude verifies findings instead of trusting the scanner.
- Guidelines 4.2 and 4.3 (minimum functionality and spam) are judgment calls that no code check can decide.
- Flutter projects only for now.

## Disclaimer

Not affiliated with, endorsed by, or sponsored by Apple, Google, or Anthropic. A clean report reduces rejection risk but **does not guarantee approval**. The stores' current guidelines are always the final authority.

## License

[MIT](LICENSE) © 2026 Husen
