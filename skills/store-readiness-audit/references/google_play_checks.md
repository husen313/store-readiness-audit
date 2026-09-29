# Google Play — check catalog

_Last verified: 29 Sep 2026._
Sources: https://support.google.com/googleplay/android-developer/answer/11926878 (target API), Play Policy Center.

`[S]` = scanner covers it. `[C]` = verify by reading code. `[M]` = Play Console / human only.

## 1. Build & upload
- **Target API** — from 31 Aug 2026, new apps and updates (phone/tablet) must target **API 36 (Android 16)**; extension possible to 1 Nov 2026. Existing apps below API 35 stop being shown to new users on newer devices. `[S]` AND-002
  - If `targetSdk = flutter.targetSdkVersion`, the value depends on the Flutter SDK version — pin it or verify the merged manifest.
  - API 36 behavior: edge-to-edge enforced, predictive back. `[C]` check `SafeArea` / system-inset handling on key screens.
- **applicationId** not `com.example.*`; permanent after first upload. `[S]` AND-001
- **Release signing** — Flutter template signs release with the debug key; must use an upload key. `[S]` AND-003
- **Format** — upload an Android App Bundle (`flutter build appbundle`). `[M]`
- **versionCode** increases each upload (the `+N` in pubspec). `[S]` GEN-001
- **Not debuggable**. `[S]` AND-004

## 2. Permissions
- **Restricted permissions** need a Play Console declaration or will be rejected: SMS/Call Log, `QUERY_ALL_PACKAGES`, `MANAGE_EXTERNAL_STORAGE`, `ACCESS_BACKGROUND_LOCATION`, `REQUEST_INSTALL_PACKAGES`, exact alarms, full-screen intents, accessibility services, foreground service types. `[S]` AND-010
- **Photo & Video permissions** — `READ_MEDIA_IMAGES`/`READ_MEDIA_VIDEO` only for apps whose core purpose needs broad access; otherwise use the Android Photo Picker (`image_picker` uses it on recent Android). `[S]` AND-010
- **Plugins merge permissions** — always check the merged manifest (`build/app/intermediates/merged_manifests/release/.../AndroidManifest.xml`) or `aapt dump permissions`. Remove unwanted ones with `tools:node="remove"`. `[C]`
- **AD_ID** — declare if using Advertising ID; answer the Advertising ID question in Play Console. `[S]` AND-011

## 3. User data
- **Privacy policy** — link in app and in store listing. `[S]` GEN-011
- **Account deletion** — apps that allow account creation must offer in-app deletion AND a web link where users can request deletion without reinstalling. `[S]` GEN-010 `[M]` web URL in Data safety form.
- **Prominent disclosure** — for data collection not reasonably expected (e.g. background location, contacts upload), show an in-app disclosure before the runtime prompt. `[C]`
- **Cleartext traffic** — avoid global `usesCleartextTraffic`. `[S]` AND-005

## 4. Payments
- **Play Billing** for digital goods/subscriptions; restore handled via `queryPurchases`. `[S]` GEN-020, GEN-022
- Subscription screens: clear price, period, trial terms, how to cancel. `[C]`

## 5. AI-generated content
- Apps generating content with AI must prevent offensive content and let users **report/flag** it in-app. `[S]` GEN-031
- Disclose AI data sharing in Data safety. `[M]`

## 6. Outside the code (always list in report)
- **Data safety form** matches actual data collection (incl. SDKs: Firebase, ads, AI provider).
- **Content rating** questionnaire, **target audience** (Families policy if under-13).
- **App access** — demo credentials for gated features.
- Store listing: screenshots of real app, no misleading claims, no "Apple"/"iOS" references.
- **Closed testing requirement** for new personal developer accounts (created after Nov 2023): 12+ testers for 14 continuous days before production access.
- Target API extension requested if needed.
