# Apple App Store — check catalog

_Last verified: 29 Sep 2026 (guidelines revised 6 Feb 2026 and 8 Jun 2026)._
Source: https://developer.apple.com/app-store/review/guidelines/

`[S]` = scanner covers it. `[C]` = verify by reading code. `[M]` = App Store Connect / human only.

## Contents
1. Build & upload requirements
2. Safety (1.x)
3. Performance & completeness (2.x)
4. Business / payments (3.x)
5. Design (4.x)
6. Privacy & legal (5.x)
7. Outside the code

## 1. Build & upload requirements
- **SDK** — since 28 Apr 2026 uploads must be built with the iOS 26 SDK (Xcode 26) or later. Check `flutter doctor` / Xcode version. `[M]`
- **Bundle ID** not `com.example.*`. `[S]` IOS-002
- **Version/build** — `pubspec.yaml` `version: x.y.z+N`, N increases every upload. `[S]` GEN-001
- **Export compliance** — `ITSAppUsesNonExemptEncryption` in Info.plist. `[S]` IOS-012
- **App icon** — 1024×1024 PNG, no alpha channel. `[S]` IOS-030
- **Privacy manifest** — `ios/Runner/PrivacyInfo.xcprivacy` in the Runner target; declares tracking domains and required-reason APIs (UserDefaults, file timestamp, system boot time, disk space) used by your *own* native code. Missing reasons trigger ITMS-91053 emails. `[S]` IOS-011

## 2. Safety (1.x)
- **1.2 User-generated content** — apps with UGC, chat, or AI-generated output need: filtering, a report mechanism, ability to block abusive users, published contact info. Feb 2026 clarified random/anonymous chat apps fall under 1.2. `[S]` GEN-031 `[C]`
- **1.3 Kids category** — no third-party analytics/ads that collect data. `[C]`
- **1.4 Physical harm** — fitness/health apps: no dangerous advice; medical claims need evidence. `[C]`

## 3. Performance & completeness (2.x)
- **2.1 Completeness** — no crashes, placeholder text, broken links, empty screens, dev URLs. Reviewer must reach all features (demo account in review notes). `[S]` GEN-040, GEN-041, GEN-060 `[C]`
  - Check permission-denied paths don't crash (e.g. `image_picker` returns null, `geolocator` throws).
  - Check offline/no-network states show a message, not a spinner forever.
- **2.3 Accurate metadata** — screenshots show real app UI; no other platforms' names (e.g. "Android") in app or metadata. `[C]` grep lib/ for "Android", "Play Store" in user-visible strings shown on iOS. `[M]`
- **2.5.1** — public APIs only. `[C]`
- **2.5.2** — no downloading executable code that changes app features (code push beyond JS/web allowances). Flag Shorebird-style patching only if it changes features/purpose. `[C]`
- **2.5.4** — background modes must be actually used. `[S]` IOS-032
- **ATS** — `NSAllowsArbitraryLoads` needs justification. `[S]` IOS-013

## 4. Business / payments (3.x)
- **3.1.1** — digital content/features/subscriptions must use IAP. Must offer **Restore Purchases**. `[S]` GEN-020, GEN-022
  - US storefront: court ruling allows buttons/links to external purchase; other storefronts still restricted. `[M]`
- **3.1.2 Subscriptions** — paywall shows: title, length, price (and per-unit price if relevant), what's included, auto-renew info, **links to Terms of Use (EULA) and Privacy Policy**; same links in App Store Connect metadata. Free trial terms must be clear. `[S]` GEN-021 `[C]` trace the paywall widget.
- **3.2.2** — no forcing ratings/reviews for features, no incentivised reviews. Use `in_app_review` only. `[C]`

## 5. Design (4.x)
- **4.2 Minimum functionality** — not a repackaged website; needs native value. `[S]` GEN-050
- **4.3 Spam** — Jun 2026: stricter; apps indistinguishable from what's widely available are rejected; saturated categories (e.g. dating, flashlight, sound effects, wallpaper, simple timers, fortune telling) need a meaningfully different experience; stale apps that don't attract users may be removed. `[M]` Mark MANUAL for crowded categories (fitness trackers, caption generators, etc.) and advise stating the differentiator in review notes.
- **4.8 Login services** — if using third-party/social login, also offer an equivalent option that limits data to name+email, allows email hiding, and doesn't track without consent (Sign in with Apple qualifies). Not required if only your own account system. `[S]` IOS-020

## 6. Privacy & legal (5.x)
- **5.1.1(i)** — privacy policy link in app and in App Store Connect. `[S]` GEN-011
- **5.1.1(ii)** — permission purpose strings specific and accurate; request permissions in context, not all at launch. `[S]` IOS-010 `[C]` check when permissions are requested.
- **5.1.1(v)** — apps with account creation must let users **initiate deletion in the app** (not just deactivate); may link to web to finish only if simple. `[S]` GEN-010 `[C]` confirm server data deletion.
- **5.1.2(i)** — get permission before sharing personal data with third parties, **explicitly including third-party AI**; tracking needs ATT. `[S]` GEN-030, IOS-021 `[C]` trace AI calls: consent must run before first request.
- **Secrets** — API keys in the bundle are extractable; not a guideline, but flag. `[S]` GEN-032

## 7. Outside the code (always list in report)
- App Privacy "nutrition labels" match actual data collection (incl. Firebase Analytics, Crashlytics, AI provider).
- Age rating questionnaire (updated rating system in 2025/26 — re-answer if prompted).
- Screenshots for required device sizes; no misleading content.
- App Review notes: demo account, how to reach gated features, differentiator (4.3), explanation of background modes.
- Support URL and privacy policy URL live.
- IAP products created, "Ready to Submit", and attached to the version.
- Developer Program License Agreement accepted (Jun 2026 revision).
