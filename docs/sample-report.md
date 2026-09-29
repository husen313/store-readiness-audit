# Sample scanner output

Raw output of `scan_app.py` on the test suite's *trap* project (a deliberately non-compliant Flutter app). In a real audit, Claude verifies these findings in the code and writes the final report using `assets/report_template.md`.

❌ FAIL: 4 | ⚠️ WARN: 6 | 🔍 MANUAL: 2 | ✅ PASS: 8 | ➖ N/A: 2

| ID | Store | Check | Guideline | Status | Evidence | Fix |
|---|---|---|---|---|---|---|
| GEN-010 | Both | In-app account deletion | Apple 5.1.1(v) / Play account deletion | ❌ FAIL | App creates accounts but no deletion flow found | Add a 'Delete account' action that deletes the auth user AND their data. Play also needs a web URL for deletion requests. |
| GEN-020 | Both | Restore purchases available | Apple 3.1.1 | ❌ FAIL | in_app_purchase used but no restore call | Add a visible 'Restore Purchases' button on the paywall/settings calling the SDK's restore method. |
| GEN-021 | Both | Subscription paywall shows Terms (EULA) + Privacy links | Apple 3.1.2 | ❌ FAIL | Missing on paywall (lib/screens/paywall_screen.dart): Terms/EULA, Privacy Policy \| found elsewhere: lib/screens/settings.dart:3 | Paywall must show price, period, what's included, and links to Terms of Use (EULA) and Privacy Policy. |
| IOS-030 | iOS | 1024×1024 App Store icon, no transparency | 2.3 / Asset validation | ❌ FAIL | No 1024×1024 PNG in AppIcon.appiconset | Generate icons (e.g. flutter_launcher_icons) with a 1024 marketing icon. |
| AND-010 | Android | Sensitive/restricted permissions justified | Permissions policy | ⚠️ WARN | android/app/src/main/AndroidManifest.xml + merged build/app/intermediates/merged_manifests/release/processReleaseManifest/AndroidManifest.xml: READ_MEDIA_IMAGES (added by a plugin): Photo & Video permissions policy — use the Photo Picker unless core feature | Remove unneeded ones — for plugin-added permissions use <uses-permission android:name="..." tools:node="remove"/> — or prepare the Play Console declaration. |
| GEN-011 | Both | Privacy policy reachable in app | Apple 5.1.1(i) / Play User Data | ⚠️ WARN | No privacy policy URL/label found | Add a Privacy Policy link (Settings/About, and on sign-up and paywall screens). Also required in store listing. |
| GEN-030 | Both | Consent before sending personal data to third-party AI | Apple 5.1.2(i) | ⚠️ WARN | google_generative_ai \| no consent UI found | Show a clear disclosure (which AI provider, what data) and get permission BEFORE the first request; list the provider in privacy policy, App Privacy labels and Play Data safety. |
| GEN-031 | Both | Way to report AI/user-generated content | Apple 1.2 / Play AI-generated content | ⚠️ WARN | No report/flag action found | Add a 'Report' action on generated output so users can flag offensive results. |
| IOS-011 | iOS | App privacy manifest (PrivacyInfo.xcprivacy) | Privacy manifest | ⚠️ WARN | No PrivacyInfo.xcprivacy in ios/Runner | Create ios/Runner/PrivacyInfo.xcprivacy (Xcode > New File > App Privacy) and add to Runner target; declare tracking domains and any required-reason APIs your native code uses. |
| IOS-012 | iOS | Export compliance key set | App Store Connect | ⚠️ WARN | ITSAppUsesNonExemptEncryption not in Info.plist | Add <key>ITSAppUsesNonExemptEncryption</key><false/> if you only use HTTPS/standard encryption; otherwise you'll answer the encryption questions on every build. |
| AND-003 | Android | Release build signed with upload key (not debug) | Play Console | 🔍 MANUAL | Couldn't find signing config | Confirm the release AAB is signed with your upload key. |
| GEN-060 | Both | Reviewer can access all features (demo account) | Apple 2.1 / Play App access | 🔍 MANUAL | App requires login | Provide a working demo account + instructions in App Review notes / Play 'App access'. |
| AND-001 | Android | applicationId is not a placeholder | Play Console | ✅ PASS | android/app/build.gradle.kts: com.acme.app |  |
| AND-002 | Android | targetSdk ≥ 36 (required from 31 Aug 2026) | Target API policy | ✅ PASS | android/app/build.gradle.kts: targetSdk 36 |  |
| AND-005 | Android | No global cleartext (HTTP) traffic | Security | ✅ PASS | Not enabled in main manifest |  |
| GEN-001 | Both | Version and build number set | Upload | ✅ PASS | pubspec.yaml version: 1.0.0+1 | Remember to bump the build number (+N) for every upload. |
| GEN-040 | Both | No placeholder content | Apple 2.1 / 2.3 | ✅ PASS | None found |  |
| GEN-041 | Both | No debug endpoints/banners in release code | Apple 2.1 | ✅ PASS | None found |  |
| IOS-002 | iOS | Bundle identifier is not a placeholder | App Store Connect | ✅ PASS | com.acme.app |  |
| IOS-013 | iOS | App Transport Security not globally disabled | 2.5 / ATS | ✅ PASS | No global ATS bypass |  |
| IOS-020 | iOS | Login services (equivalent privacy-focused option) | 4.8 | ➖ N/A | No third-party social login |  |
| IOS-021 | iOS | App Tracking Transparency prompt | 5.1.2(i) | ➖ N/A | No ads/attribution SDKs |  |