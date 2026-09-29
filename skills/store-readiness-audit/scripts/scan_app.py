#!/usr/bin/env python3
"""
Store readiness scanner for Flutter apps (App Store + Google Play).

Usage:
    python3 scan_app.py <project-root> [--store ios|android|both] [--out DIR]

Writes <out>/report.json and <out>/report.md and prints a summary.
Heuristic, text-based checks: a strong first pass that the model then verifies.
"""
import argparse
import json
import plistlib
import re
import sys
from pathlib import Path

PASS, FAIL, WARN, MANUAL, NA = "PASS", "FAIL", "WARN", "MANUAL", "N/A"
ICON = {PASS: "✅", FAIL: "❌", WARN: "⚠️", MANUAL: "🔍", NA: "➖"}

results = []


def add(cid, store, title, guideline, status, evidence="", fix=""):
    results.append(dict(id=cid, store=store, title=title, guideline=guideline,
                        status=status, evidence=evidence, fix=fix))


# ---------------------------------------------------------------- helpers
def read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def rel(root, p):
    try:
        return str(Path(p).relative_to(root))
    except ValueError:
        return str(p)


def dart_files(root):
    lib = root / "lib"
    return [p for p in lib.rglob("*.dart")] if lib.exists() else []


def arb_files(root):
    """Localization files — user-visible labels often live here, not in Dart."""
    return [p for p in root.rglob("*.arb")
            if not any(x in p.parts for x in ("build", ".dart_tool", "ios", "android"))]


def strip_dart_comments(src):
    """Remove // and /* */ comments (Dart block comments nest), keep string
    literals and newlines intact so line numbers stay correct."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        # string literal (optionally raw), single or triple quoted
        raw = c == "r" and i + 1 < n and src[i + 1] in "'\"" and (i == 0 or not (src[i - 1].isalnum() or src[i - 1] == "_"))
        if c in "'\"" or raw:
            start = i
            if raw:
                i += 1
            q = src[i]
            triple = src[i:i + 3] == q * 3
            delim = q * 3 if triple else q
            i += len(delim)
            while i < n:
                if not raw and src[i] == "\\":
                    i += 2
                    continue
                if src.startswith(delim, i):
                    i += len(delim)
                    break
                if not triple and src[i] == "\n":
                    break
                i += 1
            out.append(src[start:i])
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j == -1 else j
            continue
        if src.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    if src[i] == "\n":
                        out.append("\n")
                    i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


_cache = {}


def code_text(f):
    if f not in _cache:
        t = read(f)
        _cache[f] = strip_dart_comments(t) if str(f).endswith(".dart") else t
    return _cache[f]


def grep(files, pattern, flags=re.IGNORECASE, limit=5):
    """Return list of (file, line_no, line) matches, ignoring Dart comments."""
    rx = re.compile(pattern, flags)
    hits = []
    for f in files:
        for i, line in enumerate(code_text(f).splitlines(), 1):
            if rx.search(line):
                hits.append((f, i, line.strip()[:140]))
                if len(hits) >= limit:
                    return hits
    return hits


def in_string(word):
    """Pattern: `word` appears inside a single-line string literal."""
    return r"""['"][^'"\n]*(?:""" + word + r""")[^'"\n]*['"]"""


def fmt_hits(root, hits):
    return "; ".join(f"{rel(root, f)}:{n}" for f, n, _ in hits)


# ------------------------------------------------ default Flutter icons
# sha256 of untouched `flutter create` icons (collected from flutter/packages examples)
DEFAULT_ICON_SHA = {
    "7770183009e914112de7d8ef1d235a6a30c5834424858e0d2f8253f6b8d31926",  # iOS 1024
    "b5792ca06f48a431d4379aba2160bd5de92339fc64c6a0d3417aa359634cd905",  # iOS 1024 (older)
    "6a7c8f0d703e3682108f9662f813302236240d3f8f638bb391e32bfb96055fef",  # mipmap-hdpi
    "c7c0c0189145e4e32a401c61c9bdc615754b0264e7afae24e834bb81049eaf81",  # mipmap-mdpi
    "e14aa40904929bf313fded22cf7e7ffcbf1d1aac4263b5ef1be8bfce650397aa",  # mipmap-xhdpi
    "4d470bf22d5c17d84edc5f82516d1ba8a1c09559cd761cefb792f86d9f52b540",  # mipmap-xxhdpi
    "3c34e1f298d0c9ea3455d46db6b7759c8211a49e9ec6e44b635fc5c87dfb4180",  # mipmap-xxxhdpi
}
# 16x16 average-hash fingerprints of the Flutter logo (white-bg and dark-bg variants)
DEFAULT_ICON_AHASH = [
    0xffffffffff0ffe0ffc3ff87ff0ffe18fe30ff41ffc3ffc1ffe0fff0fffffffff,
    0xff83ff07fe0ffc1ff83ff07fe0ffc183c307e60ffc1ff81ffc1ffe0fff03ff83,
]
AHASH_THRESHOLD = 30  # of 256 bits; logo variants ≤ 40 apart from each other, unrelated icons ≥ 100


def is_default_flutter_icon(path):
    """Return (True/False/None, how). None = couldn't decide."""
    import hashlib
    try:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() in DEFAULT_ICON_SHA:
            return True, "exact match"
    except Exception:
        return None, "unreadable"
    try:
        from PIL import Image
        im = Image.open(path).convert("RGBA")
        base = Image.new("RGBA", im.size, (255, 255, 255, 255))
        base.alpha_composite(im)
        g = base.convert("L").resize((16, 16), Image.LANCZOS)
        px = g.tobytes()
        m = sum(px) / len(px)
        h = int("".join("1" if v > m else "0" for v in px), 2)
        d = min(bin(h ^ ref).count("1") for ref in DEFAULT_ICON_AHASH)
        return d <= AHASH_THRESHOLD, f"fingerprint distance {d}"
    except ImportError:
        return False, "no exact match (Pillow missing for fuzzy check)"
    except Exception as e:
        return None, str(e)


def parse_deps(pubspec_text):
    deps = set()
    section = None
    for line in pubspec_text.splitlines():
        if re.match(r"^(dependencies|dev_dependencies|dependency_overrides):", line):
            section = line.split(":")[0]
            continue
        if re.match(r"^\S", line):
            section = None
        if section == "dependencies":
            m = re.match(r"^  ([a-zA-Z0-9_]+):", line)
            if m:
                deps.add(m.group(1))
    return deps


# ------------------------------------------------------- plugin → iOS keys
# plugin: [(Info.plist key, required?)]  required=False means "usually needed"
PLUGIN_IOS_KEYS = {
    "image_picker": [("NSPhotoLibraryUsageDescription", True), ("NSCameraUsageDescription", True),
                     ("NSMicrophoneUsageDescription", False)],
    "camera": [("NSCameraUsageDescription", True), ("NSMicrophoneUsageDescription", False)],
    "mobile_scanner": [("NSCameraUsageDescription", True)],
    "qr_code_scanner": [("NSCameraUsageDescription", True)],
    "photo_manager": [("NSPhotoLibraryUsageDescription", True)],
    "gal": [("NSPhotoLibraryAddUsageDescription", True)],
    "image_gallery_saver": [("NSPhotoLibraryAddUsageDescription", True)],
    "geolocator": [("NSLocationWhenInUseUsageDescription", True)],
    "location": [("NSLocationWhenInUseUsageDescription", True)],
    "google_maps_flutter": [("NSLocationWhenInUseUsageDescription", False)],
    "flutter_contacts": [("NSContactsUsageDescription", True)],
    "contacts_service": [("NSContactsUsageDescription", True)],
    "local_auth": [("NSFaceIDUsageDescription", True)],
    "speech_to_text": [("NSSpeechRecognitionUsageDescription", True), ("NSMicrophoneUsageDescription", True)],
    "record": [("NSMicrophoneUsageDescription", True)],
    "flutter_sound": [("NSMicrophoneUsageDescription", True)],
    "health": [("NSHealthShareUsageDescription", True), ("NSHealthUpdateUsageDescription", False)],
    "flutter_blue_plus": [("NSBluetoothAlwaysUsageDescription", True)],
    "flutter_reactive_ble": [("NSBluetoothAlwaysUsageDescription", True)],
    "device_calendar": [("NSCalendarsFullAccessUsageDescription", True)],
    "add_2_calendar": [("NSCalendarsWriteOnlyAccessUsageDescription", False)],
    "app_tracking_transparency": [("NSUserTrackingUsageDescription", True)],
    "pedometer": [("NSMotionUsageDescription", True)],
    "sensors_plus": [],
}

ADS_TRACKING_SDKS = {"google_mobile_ads", "facebook_app_events", "appsflyer_sdk", "adjust_sdk",
                     "applovin_max", "unity_ads_plugin", "ironsource_mediation", "branch_sdk"}
SOCIAL_LOGIN = {"google_sign_in", "flutter_facebook_auth", "twitter_login", "flutter_line_sdk",
                "firebase_ui_oauth_google", "firebase_ui_oauth_facebook"}
APPLE_LOGIN = {"sign_in_with_apple", "firebase_ui_oauth_apple"}
IAP_SDKS = {"in_app_purchase", "purchases_flutter", "flutter_inapp_purchase", "adapty_flutter",
            "superwallkit_flutter", "qonversion_flutter", "glassfy_flutter"}
EXTERNAL_PAY = {"flutter_stripe", "razorpay_flutter", "flutter_paypal", "flutter_braintree",
                "pay", "paystack_manager", "flutterwave_standard"}
AI_SDKS = {"google_generative_ai", "firebase_ai", "firebase_vertexai", "dart_openai", "openai_dart",
           "anthropic_sdk_dart", "langchain", "langchain_openai", "mistralai_dart"}
AI_URLS = r"api\.openai\.com|api\.anthropic\.com|generativelanguage\.googleapis\.com|api\.groq\.com|api\.mistral\.ai|openrouter\.ai|api\.deepseek\.com"
ACCOUNT_SDKS = {"firebase_auth", "supabase_flutter", "amplify_auth_cognito", "appwrite", "pocketbase"}
PLACEHOLDER_RX = in_string(r"lorem ipsum|coming soon|under construction|\bTODO\b|placeholder text|test test")


# ------------------------------------------------------------------ iOS
def ios_checks(root, deps, dfiles):
    ios = root / "ios"
    if not ios.exists():
        add("IOS-000", "iOS", "iOS project folder present", "-", FAIL, "ios/ not found",
            "Run `flutter create --platforms=ios .`")
        return
    plist_path = ios / "Runner" / "Info.plist"
    plist = {}
    try:
        plist = plistlib.loads(plist_path.read_bytes())
    except Exception as e:
        add("IOS-001", "iOS", "Info.plist readable", "-", FAIL, f"{rel(root, plist_path)}: {e}",
            "Fix the Info.plist XML.")
    pbx = read(ios / "Runner.xcodeproj" / "project.pbxproj")

    # Bundle ID
    ids = set(re.findall(r"PRODUCT_BUNDLE_IDENTIFIER = ([^;]+);", pbx))
    main_ids = {i.strip('"') for i in ids if "RunnerTests" not in i}
    bad = [i for i in main_ids if i.startswith("com.example")]
    if bad:
        add("IOS-002", "iOS", "Bundle identifier is not a placeholder", "App Store Connect", FAIL,
            f"project.pbxproj: {', '.join(bad)}", "Set a unique reverse-DNS bundle ID you own (e.g. com.yourco.app).")
    elif main_ids:
        add("IOS-002", "iOS", "Bundle identifier is not a placeholder", "App Store Connect", PASS,
            ", ".join(sorted(main_ids)))

    # Permission strings
    missing, weak, ok = [], [], []
    for plugin, keys in PLUGIN_IOS_KEYS.items():
        if plugin not in deps:
            continue
        for key, required in keys:
            val = plist.get(key)
            if val is None:
                (missing if required else weak).append(f"{key} (for {plugin}{'' if required else ', if used'})")
            elif len(str(val).strip()) < 25 or re.search(r"todo|lorem|\$\(|needs? access$|test", str(val), re.I):
                weak.append(f"{key} too vague: \"{val}\"")
            else:
                ok.append(key)
    # Also flag any existing usage strings that look placeholder-ish
    for k, v in plist.items():
        if k.endswith("UsageDescription") and k not in ok and isinstance(v, str) and len(v.strip()) < 25:
            if not any(k in w for w in weak):
                weak.append(f"{k} too vague: \"{v}\"")
    if missing:
        add("IOS-010", "iOS", "Permission purpose strings for used plugins", "5.1.1(ii)", FAIL,
            "Missing in Info.plist: " + "; ".join(missing) + (" | Also vague: " + "; ".join(weak) if weak else ""),
            "Add each key with a specific purpose, e.g. \"Used to attach a progress photo to your workout log.\" "
            "Missing keys crash the app when the permission is requested.")
    elif weak:
        add("IOS-010", "iOS", "Permission purpose strings for used plugins", "5.1.1(ii)", WARN,
            "; ".join(weak), "Make each string say what feature uses the data and why. Vague strings are a common rejection.")
    elif ok:
        add("IOS-010", "iOS", "Permission purpose strings for used plugins", "5.1.1(ii)", PASS, ", ".join(ok))

    # Privacy manifest
    manifests = [p for p in ios.rglob("PrivacyInfo.xcprivacy") if "Pods" not in p.parts]
    if manifests:
        txt = read(manifests[0])
        note = rel(root, manifests[0])
        if "shared_preferences" in deps and "NSPrivacyAccessedAPICategoryUserDefaults" not in txt:
            add("IOS-011", "iOS", "App privacy manifest (PrivacyInfo.xcprivacy)", "ITMS-91053 / Privacy manifest",
                WARN, f"{note} has no UserDefaults reason declared",
                "If your own Swift/ObjC code uses UserDefaults, declare NSPrivacyAccessedAPICategoryUserDefaults (reason CA92.1).")
        elif "PrivacyInfo.xcprivacy" not in pbx:
            add("IOS-011", "iOS", "App privacy manifest (PrivacyInfo.xcprivacy)", "Privacy manifest", WARN,
                f"{note} exists but isn't referenced in project.pbxproj",
                "Add the file to the Runner target in Xcode (drag in, tick 'Runner').")
        else:
            add("IOS-011", "iOS", "App privacy manifest (PrivacyInfo.xcprivacy)", "Privacy manifest", PASS, note)
    else:
        add("IOS-011", "iOS", "App privacy manifest (PrivacyInfo.xcprivacy)", "Privacy manifest", WARN,
            "No PrivacyInfo.xcprivacy in ios/Runner",
            "Create ios/Runner/PrivacyInfo.xcprivacy (Xcode > New File > App Privacy) and add to Runner target; "
            "declare tracking domains and any required-reason APIs your native code uses.")

    # Export compliance
    if "ITSAppUsesNonExemptEncryption" in plist:
        add("IOS-012", "iOS", "Export compliance key set", "App Store Connect", PASS,
            f"ITSAppUsesNonExemptEncryption = {plist['ITSAppUsesNonExemptEncryption']}")
    else:
        add("IOS-012", "iOS", "Export compliance key set", "App Store Connect", WARN,
            "ITSAppUsesNonExemptEncryption not in Info.plist",
            "Add <key>ITSAppUsesNonExemptEncryption</key><false/> if you only use HTTPS/standard encryption; "
            "otherwise you'll answer the encryption questions on every build.")

    # ATS
    ats = plist.get("NSAppTransportSecurity", {}) or {}
    if ats.get("NSAllowsArbitraryLoads"):
        add("IOS-013", "iOS", "App Transport Security not globally disabled", "2.5 / ATS", WARN,
            "NSAllowsArbitraryLoads = true", "Remove it or scope to NSExceptionDomains; Apple asks for justification.")
    else:
        add("IOS-013", "iOS", "App Transport Security not globally disabled", "2.5 / ATS", PASS, "No global ATS bypass")

    # Sign in with Apple / 4.8
    social = deps & SOCIAL_LOGIN
    if social:
        if deps & APPLE_LOGIN:
            add("IOS-020", "iOS", "Login services (equivalent privacy-focused option)", "4.8", PASS,
                f"{', '.join(social)} + {', '.join(deps & APPLE_LOGIN)}")
        else:
            add("IOS-020", "iOS", "Login services (equivalent privacy-focused option)", "4.8", FAIL,
                f"Third-party login ({', '.join(social)}) without Sign in with Apple",
                "Add sign_in_with_apple (or another option meeting 4.8: limited data, private email, no ad tracking). "
                "Exempt only if login is exclusively your own account system / enterprise / education.")
    else:
        add("IOS-020", "iOS", "Login services (equivalent privacy-focused option)", "4.8", NA, "No third-party social login")

    # ATT
    trackers = deps & ADS_TRACKING_SDKS
    if trackers:
        if "app_tracking_transparency" in deps and plist.get("NSUserTrackingUsageDescription"):
            add("IOS-021", "iOS", "App Tracking Transparency prompt", "5.1.2(i)", PASS,
                f"{', '.join(trackers)} + ATT")
        else:
            add("IOS-021", "iOS", "App Tracking Transparency prompt", "5.1.2(i)", WARN,
                f"Ads/attribution SDK ({', '.join(trackers)}) without ATT plugin + NSUserTrackingUsageDescription",
                "Add app_tracking_transparency, request before tracking, add the purpose string. "
                "If you don't track, configure SDKs for non-personalized mode and say so in privacy labels.")
    else:
        add("IOS-021", "iOS", "App Tracking Transparency prompt", "5.1.2(i)", NA, "No ads/attribution SDKs")

    # Push entitlement
    if deps & {"firebase_messaging", "onesignal_flutter"}:
        ent = list((ios / "Runner").glob("*.entitlements"))
        has = any("aps-environment" in read(e) for e in ent)
        add("IOS-022", "iOS", "Push notification entitlement", "Capabilities",
            PASS if has else WARN,
            "aps-environment found" if has else "firebase_messaging used but no aps-environment entitlement",
            "" if has else "Enable Push Notifications capability in Xcode (Signing & Capabilities).")

    # Firebase config
    if "firebase_core" in deps:
        gs = (ios / "Runner" / "GoogleService-Info.plist").exists()
        opts = (root / "lib" / "firebase_options.dart").exists()
        add("IOS-023", "iOS", "Firebase iOS config present", "2.1", PASS if (gs or opts) else FAIL,
            "GoogleService-Info.plist / firebase_options.dart" if (gs or opts) else "No iOS Firebase config",
            "" if (gs or opts) else "Run `flutterfire configure` or add GoogleService-Info.plist to Runner.")

    # App icon (1024, no alpha)
    iconset = ios / "Runner" / "Assets.xcassets" / "AppIcon.appiconset"
    big = [p for p in iconset.glob("*.png")] if iconset.exists() else []
    big1024 = None
    try:
        from PIL import Image
        for p in big:
            with Image.open(p) as im:
                if im.size == (1024, 1024):
                    big1024 = (p, im.mode, im.getextrema() if im.mode == "RGBA" else None)
                    break
        if not big1024:
            add("IOS-030", "iOS", "1024×1024 App Store icon, no transparency", "2.3 / Asset validation", FAIL,
                "No 1024×1024 PNG in AppIcon.appiconset", "Generate icons (e.g. flutter_launcher_icons) with a 1024 marketing icon.")
        else:
            p, mode, ext = big1024
            has_alpha = mode in ("RGBA", "LA") and ext and ext[3][0] < 255
            add("IOS-030", "iOS", "1024×1024 App Store icon, no transparency", "Asset validation",
                FAIL if has_alpha else PASS, f"{rel(root, p)} mode={mode}",
                "Flatten the icon to RGB (flutter_launcher_icons: remove_alpha_ios: true)." if has_alpha else "")
    except ImportError:
        add("IOS-030", "iOS", "1024×1024 App Store icon, no transparency", "Asset validation", MANUAL,
            "Pillow not installed", "pip install pillow, or check the icon in Xcode.")
    # Default Flutter icon?
    if big:
        target = next((p for p in big if "1024" in p.name), big[0])
        dflt, how = is_default_flutter_icon(target)
        if dflt is None:
            add("IOS-031", "iOS", "App icon is not the default Flutter icon", "2.1 / 2.3", MANUAL,
                f"{rel(root, target)}: {how}", "Open AppIcon in Xcode and check.")
        else:
            add("IOS-031", "iOS", "App icon is not the default Flutter icon", "2.1 / 2.3",
                FAIL if dflt else PASS, f"{rel(root, target)} ({how})",
                "Replace with your own artwork (flutter_launcher_icons)." if dflt else "")

    # Background modes
    modes = plist.get("UIBackgroundModes") or []
    if modes:
        add("IOS-032", "iOS", "Declared background modes are used", "2.5.4", MANUAL,
            f"UIBackgroundModes: {', '.join(modes)}",
            "Remove any mode the app doesn't actively need; reviewers test it (e.g. 'audio' must play audio in background).")


# -------------------------------------------------------------- Android
def android_checks(root, deps):
    app = root / "android" / "app"
    if not app.exists():
        add("AND-000", "Android", "Android project folder present", "-", FAIL, "android/app not found",
            "Run `flutter create --platforms=android .`")
        return
    gradle_p = app / "build.gradle.kts" if (app / "build.gradle.kts").exists() else app / "build.gradle"
    gradle = read(gradle_p)
    gname = rel(root, gradle_p)

    # applicationId
    m = re.search(r"applicationId\s*=?\s*[\"']([^\"']+)", gradle)
    if m:
        aid = m.group(1)
        add("AND-001", "Android", "applicationId is not a placeholder", "Play Console",
            FAIL if aid.startswith("com.example") else PASS, f"{gname}: {aid}",
            "Play rejects com.example.*; set your own ID (can't change after first upload)." if aid.startswith("com.example") else "")

    # targetSdk
    t = re.search(r"targetSdk(?:Version)?\s*=?\s*([\w.]+)", gradle)
    if t:
        val = t.group(1)
        if val.isdigit():
            n = int(val)
            add("AND-002", "Android", "targetSdk ≥ 36 (required from 31 Aug 2026)", "Target API policy",
                PASS if n >= 36 else FAIL, f"{gname}: targetSdk {n}",
                "" if n >= 36 else "Set targetSdk = 36 and test Android 16 behavior changes (edge-to-edge, predictive back).")
        else:
            add("AND-002", "Android", "targetSdk ≥ 36 (required from 31 Aug 2026)", "Target API policy", MANUAL,
                f"{gname}: targetSdk = {val} (inherits from Flutter SDK)",
                "Check the value your Flutter version sets, or pin targetSdk = 36 explicitly.")

    # Release signing
    rel_block = re.search(r"release\s*\{([^}]*)\}", gradle, re.S)
    if rel_block and re.search(r"signingConfig[s]?\s*=?\s*signingConfigs\.(getByName\(\"debug\"\)|debug)", rel_block.group(1)):
        add("AND-003", "Android", "Release build signed with upload key (not debug)", "Play Console", FAIL,
            f"{gname}: release uses debug signingConfig",
            "Create an upload keystore, key.properties, and a release signingConfig. Play rejects debug-signed bundles.")
    elif "signingConfigs" in gradle:
        add("AND-003", "Android", "Release build signed with upload key (not debug)", "Play Console", PASS,
            f"{gname}: custom signing config")
    else:
        add("AND-003", "Android", "Release build signed with upload key (not debug)", "Play Console", MANUAL,
            "Couldn't find signing config", "Confirm the release AAB is signed with your upload key.")

    # Manifest (main + merged, because plugins add permissions at build time)
    man_p = app / "src" / "main" / "AndroidManifest.xml"
    man = read(man_p)
    mname = rel(root, man_p)
    merged_p, merged, stale = None, "", False
    inter = root / "build" / "app" / "intermediates"
    if inter.exists():
        cands = [p for p in inter.rglob("AndroidManifest.xml")
                 if "merged_manifest" in str(p) and "release" in str(p).lower()]
        if cands:
            merged_p = max(cands, key=lambda p: p.stat().st_mtime)
            merged = read(merged_p)
            lock = root / "pubspec.lock"
            stale = lock.exists() and lock.stat().st_mtime > merged_p.stat().st_mtime
    both = man + "\n" + merged

    if 'android:debuggable="true"' in both:
        add("AND-004", "Android", "Not debuggable", "Play Console", FAIL,
            rel(root, merged_p) if merged_p and 'debuggable="true"' in merged else mname,
            "Remove android:debuggable; build with --release.")
    if 'usesCleartextTraffic="true"' in man:
        add("AND-005", "Android", "No global cleartext (HTTP) traffic", "Security", WARN, mname,
            "Remove usesCleartextTraffic or use a network_security_config scoped to specific domains.")
    else:
        add("AND-005", "Android", "No global cleartext (HTTP) traffic", "Security", PASS, "Not enabled in main manifest")

    sensitive = {
        "QUERY_ALL_PACKAGES": "Package visibility policy — needs declaration; use <queries> instead",
        "MANAGE_EXTERNAL_STORAGE": "All files access — needs declaration; rarely approved",
        "ACCESS_BACKGROUND_LOCATION": "Background location — declaration + video required",
        "READ_SMS": "SMS/Call Log policy — restricted", "SEND_SMS": "SMS/Call Log policy — restricted",
        "READ_CALL_LOG": "SMS/Call Log policy — restricted",
        "REQUEST_INSTALL_PACKAGES": "Restricted — needs core-functionality justification",
        "READ_MEDIA_IMAGES": "Photo & Video permissions policy — use the Photo Picker unless core feature",
        "READ_MEDIA_VIDEO": "Photo & Video permissions policy — use the Photo Picker unless core feature",
        "USE_EXACT_ALARM": "Exact alarm — only for alarm/calendar apps",
        "SCHEDULE_EXACT_ALARM": "Exact alarm — declare use or switch to inexact",
        "USE_FULL_SCREEN_INTENT": "Full-screen intent — only calling/alarm apps",
        "BIND_ACCESSIBILITY_SERVICE": "Accessibility API policy — declaration required",
    }
    perm_rx = r'uses-permission[^>]*android:name="android\.permission\.([A-Z_]+)"'
    main_perms = set(re.findall(perm_rx, man))
    # tools:node="remove" in main manifest strips a permission from the merge
    removed = set(re.findall(r'android:name="android\.permission\.([A-Z_]+)"[^>]*tools:node="remove"', man)) | \
              set(re.findall(r'tools:node="remove"[^>]*android:name="android\.permission\.([A-Z_]+)"', man))
    merged_perms = set(re.findall(perm_rx, merged)) - removed
    perms = (main_perms - removed) | merged_perms

    def label(p):
        return f"{p} (added by a plugin)" if p in merged_perms and p not in main_perms else p
    flagged = [f"{label(p)}: {sensitive[p]}" for p in sorted(perms) if p in sensitive]
    fg = [label(p) for p in sorted(perms) if p.startswith("FOREGROUND_SERVICE_")]
    if fg:
        flagged.append(f"{', '.join(fg)}: foreground service types need a Play Console declaration")
    src = f"{mname} + merged {rel(root, merged_p)}" if merged_p else mname
    stale_note = " (merged manifest older than pubspec.lock — rebuild to refresh)" if stale else ""
    if flagged:
        add("AND-010", "Android", "Sensitive/restricted permissions justified", "Permissions policy", WARN,
            f"{src}{stale_note}: " + " | ".join(flagged),
            "Remove unneeded ones — for plugin-added permissions use "
            "<uses-permission android:name=\"...\" tools:node=\"remove\"/> — or prepare the Play Console declaration.")
    elif merged_p and not stale:
        add("AND-010", "Android", "Sensitive/restricted permissions justified", "Permissions policy", PASS,
            f"No restricted permissions in {src}")
    else:
        add("AND-010", "Android", "Sensitive/restricted permissions justified", "Permissions policy", MANUAL,
            f"Main manifest clean, but {'merged manifest is stale' if stale else 'no merged manifest found'} — "
            "plugins can add permissions at build time",
            "Run `flutter build appbundle --release`, then re-run the audit (or check Play Console > App bundle explorer).")

    # AD_ID
    if deps & ADS_TRACKING_SDKS:
        has_adid = "AD_ID" in both
        add("AND-011", "Android", "AD_ID permission declared for ads SDK", "Advertising ID policy",
            PASS if has_adid else (WARN if merged_p else MANUAL),
            ("AD_ID present" if has_adid else "Ads SDK without AD_ID") + (" (merged)" if merged_p else " (main only)"),
            "" if has_adid else "Confirm in merged manifest and answer the 'Advertising ID' form in Play Console.")

    # Default launcher icon
    res = app / "src" / "main" / "res"
    icons = sorted(res.glob("mipmap-*/ic_launcher.png"), key=lambda p: -p.stat().st_size) if res.exists() else []
    if icons:
        dflt, how = is_default_flutter_icon(icons[0])
        add("AND-020", "Android", "Launcher icon is not the default Flutter icon", "Store listing / Metadata policy",
            MANUAL if dflt is None else (FAIL if dflt else PASS), f"{rel(root, icons[0])} ({how})",
            "Replace with your own artwork (flutter_launcher_icons)." if dflt else "")

    # Firebase config
    if "firebase_core" in deps:
        gs = (app / "google-services.json").exists() or (root / "lib" / "firebase_options.dart").exists()
        add("AND-012", "Android", "Firebase Android config present", "-", PASS if gs else FAIL,
            "google-services.json / firebase_options.dart" if gs else "Missing",
            "" if gs else "Run `flutterfire configure`.")


# --------------------------------------------------------------- shared
def shared_checks(root, deps, dfiles, stores):
    tag = "Both" if len(stores) == 2 else stores[0]

    # Version
    pub = read(root / "pubspec.yaml")
    v = re.search(r"^version:\s*(\S+)", pub, re.M)
    if v and "+" in v.group(1):
        add("GEN-001", tag, "Version and build number set", "Upload", PASS, f"pubspec.yaml version: {v.group(1)}",
            "Remember to bump the build number (+N) for every upload.")
    else:
        add("GEN-001", tag, "Version and build number set", "Upload", WARN,
            f"pubspec.yaml version: {v.group(1) if v else 'missing'}", "Use version: 1.2.0+12 format.")

    arbs = arb_files(root)
    ui_files = [f for f in dfiles if "Widget build(" in code_text(f)]

    # Account deletion
    creates_accounts = bool(deps & ACCOUNT_SDKS) and bool(grep(dfiles,
        r"createUserWithEmailAndPassword|\bsignUp\s*\(|signInWith(Credential|Provider|Apple|Google)\s*\(|registerUser\s*\(", limit=1))
    # custom backends: sign-up endpoints called via http/dio
    if not creates_accounts:
        creates_accounts = bool(grep(dfiles, in_string(r"/(sign-?up|register)\b"), limit=1))
    if creates_accounts:
        del_call = grep(dfiles,
            r"(currentUser|user)[!?]?\.delete\s*\(\s*\)|\bdelete(User|Account)\w*\s*\(|auth\.admin\.deleteUser|"
            r"httpsCallable\(\s*['\"][^'\"]*delete[^'\"]*['\"]|rpc\(\s*['\"][^'\"]*delete[^'\"]*['\"]|"
            + in_string(r"/(delete-?account|account/delete|users?/me)"), limit=3)
        del_label = grep(ui_files + arbs, in_string(r"delete (my |your )?account"), limit=2)
        if del_call and del_label:
            add("GEN-010", tag, "In-app account deletion", "Apple 5.1.1(v) / Play account deletion", PASS,
                f"call: {fmt_hits(root, del_call)} | UI: {fmt_hits(root, del_label)}",
                "Confirm it also deletes server-side data, not just the auth user.")
        elif del_call or del_label:
            add("GEN-010", tag, "In-app account deletion", "Apple 5.1.1(v) / Play account deletion", WARN,
                ("call found, no 'Delete account' label: " + fmt_hits(root, del_call)) if del_call
                else ("label found, no deletion call: " + fmt_hits(root, del_label)),
                "Trace the flow: a visible 'Delete account' action must actually delete the account and its data.")
        else:
            add("GEN-010", tag, "In-app account deletion", "Apple 5.1.1(v) / Play account deletion", FAIL,
                "App creates accounts but no deletion flow found",
                "Add a 'Delete account' action that deletes the auth user AND their data. Play also needs a web URL for deletion requests.")
    else:
        add("GEN-010", tag, "In-app account deletion", "Apple 5.1.1(v) / Play account deletion", NA, "No account creation detected")

    # Privacy policy link — must be a real string (URL or label), not a comment or variable name
    pp_rx = in_string(r"privacy[-_ ]?policy|/privacy|privacy\.html")
    pp = grep(dfiles + arbs, pp_rx, limit=2)
    add("GEN-011", tag, "Privacy policy reachable in app", "Apple 5.1.1(i) / Play User Data", PASS if pp else WARN,
        fmt_hits(root, pp) + " (confirm it's shown on a screen)" if pp else "No privacy policy URL/label found",
        "" if pp else "Add a Privacy Policy link (Settings/About, and on sign-up and paywall screens). Also required in store listing.")

    # IAP
    iap = deps & IAP_SDKS
    if iap:
        restore_call = grep(dfiles, r"\b(restorePurchases|restoreTransactions|restoreCompletedTransactions)\s*\(", limit=2)
        restore_label = grep(ui_files + arbs, in_string(r"restore"), limit=2) or \
            grep(ui_files, r"\.restore\w*\b(?!\s*\()", limit=2)  # l10n getter e.g. l10n.restorePurchases
        if restore_call and restore_label:
            add("GEN-020", tag, "Restore purchases available", "Apple 3.1.1", PASS,
                f"call: {fmt_hits(root, restore_call)} | UI: {fmt_hits(root, restore_label)}")
        elif restore_call:
            add("GEN-020", tag, "Restore purchases available", "Apple 3.1.1", WARN,
                f"restore call at {fmt_hits(root, restore_call)} but no visible 'Restore' label found",
                "Make sure a 'Restore Purchases' button is visible on the paywall or in Settings.")
        else:
            add("GEN-020", tag, "Restore purchases available", "Apple 3.1.1", FAIL,
                f"{', '.join(iap)} used but no restore call",
                "Add a visible 'Restore Purchases' button on the paywall/settings calling the SDK's restore method.")

        # Paywall scoping: legal links must be on the paywall, not just somewhere in the app
        iap_imports = r"package:(in_app_purchase|purchases_flutter|flutter_inapp_purchase|adapty_flutter|qonversion_flutter|glassfy_flutter)"
        name_rx = re.compile(r"paywall|subscri|premium|purchase|upgrade|pro_(screen|page|view)|store_(screen|page)", re.I)
        paywall = [f for f in ui_files if name_rx.search(f.name) or re.search(iap_imports, code_text(f))
                   or re.search(r"class \w*(Paywall|Subscription|Premium|Upgrade)\w*", code_text(f))]
        terms_rx = in_string(r"terms|eula|stdeula")
        if "purchases_ui_flutter" in deps or grep(dfiles, r"\bPaywallView\b|presentPaywall", limit=1):
            add("GEN-021", tag, "Subscription paywall shows Terms (EULA) + Privacy links", "Apple 3.1.2", MANUAL,
                "RevenueCat Paywalls UI — links are configured in the RevenueCat dashboard",
                "Check the paywall template has Terms of Use and Privacy Policy URLs set.")
        elif not paywall:
            add("GEN-021", tag, "Subscription paywall shows Terms (EULA) + Privacy links", "Apple 3.1.2", MANUAL,
                "Couldn't identify the paywall screen", "Open the paywall and confirm price, period, Terms and Privacy links.")
        else:
            pw_terms, pw_pp = grep(paywall, terms_rx, limit=2), grep(paywall, pp_rx, limit=2)
            legal_widget = grep(paywall, r"\b\w*(Legal|Terms|Policy|Footer)\w*\s*\(", flags=0, limit=2)
            subs = grep(paywall + arbs, r"subscri|monthly|yearly|annual|per month|/month|auto-?renew", limit=1)
            pw = ", ".join(rel(root, f) for f in paywall[:3])
            if pw_terms and pw_pp:
                add("GEN-021", tag, "Subscription paywall shows Terms (EULA) + Privacy links", "Apple 3.1.2", PASS,
                    f"paywall: {fmt_hits(root, pw_terms + pw_pp)}")
            elif legal_widget:
                add("GEN-021", tag, "Subscription paywall shows Terms (EULA) + Privacy links", "Apple 3.1.2", MANUAL,
                    f"paywall ({pw}) uses shared widget {fmt_hits(root, legal_widget)}",
                    "Confirm that widget shows both Terms of Use (EULA) and Privacy Policy links.")
            else:
                elsewhere = grep(dfiles + arbs, terms_rx, limit=1)
                missing = [x for x, ok in (("Terms/EULA", pw_terms), ("Privacy Policy", pw_pp)) if not ok]
                add("GEN-021", tag, "Subscription paywall shows Terms (EULA) + Privacy links", "Apple 3.1.2",
                    FAIL if subs else WARN,
                    f"Missing on paywall ({pw}): {', '.join(missing)}"
                    + (f" | found elsewhere: {fmt_hits(root, elsewhere)}" if elsewhere else ""),
                    "Paywall must show price, period, what's included, and links to Terms of Use (EULA) and Privacy Policy.")
    else:
        add("GEN-020", tag, "Restore purchases available", "Apple 3.1.1", NA, "No IAP SDK")

    ext = deps & EXTERNAL_PAY
    if ext:
        add("GEN-022", tag, "Digital goods use store billing", "Apple 3.1.1 / Play Payments", MANUAL,
            f"External payment SDK: {', '.join(ext)}",
            "OK for physical goods/services. If it unlocks digital content or features, you must use IAP / Play Billing "
            "(US App Store link-out rules differ — check current guidance).")

    # AI
    ai_dep = deps & AI_SDKS
    ai_url = grep(dfiles, AI_URLS, limit=2)
    if ai_dep or ai_url:
        consent = grep(dfiles + arbs, r"\b(hasAiConsent|aiConsent|ai_consent|acceptedAi\w*|showAiDisclosure)\b|"
                       + in_string(r"(share|send)[^'\"]*(with|to) (an? )?(AI|OpenAI|Gemini|Google|Anthropic|Claude)|AI (provider|service)"), limit=2)
        ev = ", ".join(ai_dep) + ("; " if ai_dep and ai_url else "") + fmt_hits(root, ai_url)
        add("GEN-030", tag, "Consent before sending personal data to third-party AI", "Apple 5.1.2(i)",
            MANUAL if consent else WARN, ev + (f" | consent hints: {fmt_hits(root, consent)}" if consent else " | no consent UI found"),
            "Show a clear disclosure (which AI provider, what data) and get permission BEFORE the first request; "
            "list the provider in privacy policy, App Privacy labels and Play Data safety.")
        report = grep(ui_files + arbs,
            r"\b(reportContent|report(Ai|Generated|Message|Post|Response|Output|Caption|Result|Abuse|User)|flagContent)\b|"
            + in_string(r"\b(report|flag)( this| content| response| message| result| post| caption| output| as inappropriate| abuse)?\b"),
            limit=1)
        add("GEN-031", tag, "Way to report AI/user-generated content", "Apple 1.2 / Play AI-generated content",
            PASS if report else WARN, fmt_hits(root, report) + " (confirm it's on generated output)" if report else "No report/flag action found",
            "" if report else "Add a 'Report' action on generated output so users can flag offensive results.")
        keys = grep([f for f in dfiles if f.name != "firebase_options.dart"], r"(sk-[A-Za-z0-9_\-]{20,}|sk-ant-[A-Za-z0-9_\-]{20,}|AIza[0-9A-Za-z_\-]{30,})", flags=0, limit=2)
        if keys:
            add("GEN-032", tag, "No API secrets hardcoded in app", "Security", FAIL, fmt_hits(root, keys),
                "Move provider keys to a backend/proxy (e.g. Cloud Function). Keys in the binary are extractable.")

    # Placeholder / debug
    ph = grep(dfiles + arbs, PLACEHOLDER_RX, limit=4)
    add("GEN-040", tag, "No placeholder content", "Apple 2.1 / 2.3", WARN if ph else PASS,
        fmt_hits(root, ph) if ph else "None found", "Replace placeholder text and unfinished screens." if ph else "")
    dbg = grep(dfiles, r"debugShowCheckedModeBanner:\s*true|https?://(localhost|127\.0\.0\.1|10\.0\.2\.2)|http://192\.168", limit=4)
    add("GEN-041", tag, "No debug endpoints/banners in release code", "Apple 2.1", WARN if dbg else PASS,
        fmt_hits(root, dbg) if dbg else "None found", "Gate dev URLs behind kReleaseMode / flavors." if dbg else "")

    # WebView-only
    if "webview_flutter" in deps or "flutter_inappwebview" in deps:
        if len(dfiles) < 6:
            add("GEN-050", tag, "Not just a website wrapper", "Apple 4.2", WARN,
                f"WebView plugin + only {len(dfiles)} Dart files",
                "Add native value (offline mode, push, native UI) or Apple will reject under 4.2.")

    # Login wall → demo account
    if creates_accounts:
        add("GEN-060", tag, "Reviewer can access all features (demo account)", "Apple 2.1 / Play App access", MANUAL,
            "App requires login", "Provide a working demo account + instructions in App Review notes / Play 'App access'.")


# --------------------------------------------------------------- report
def write_report(root, out, stores):
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    order = {FAIL: 0, WARN: 1, MANUAL: 2, PASS: 3, NA: 4}
    lines = [f"# Scanner results — {root.name}", ""]
    counts = {s: sum(1 for r in results if r["status"] == s) for s in order}
    lines.append(" | ".join(f"{ICON[s]} {s}: {counts[s]}" for s in order))
    lines.append("")
    lines.append("| ID | Store | Check | Guideline | Status | Evidence | Fix |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: (order[r["status"]], r["id"])):
        esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['id']} | {r['store']} | {esc(r['title'])} | {esc(r['guideline'])} | "
                     f"{ICON[r['status']]} {r['status']} | {esc(r['evidence'])} | {esc(r['fix'])} |")
    (out / "report.md").write_text("\n".join(lines))
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--store", choices=["ios", "android", "both"], default="both")
    ap.add_argument("--out", default="audit")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not (root / "pubspec.yaml").exists():
        cand = list(root.rglob("pubspec.yaml"))
        cand = [c for c in cand if ".dart_tool" not in c.parts and "ios" not in c.parts]
        if not cand:
            sys.exit("pubspec.yaml not found — is this a Flutter project?")
        root = sorted(cand, key=lambda c: len(c.parts))[0].parent
    deps = parse_deps(read(root / "pubspec.yaml"))
    dfiles = dart_files(root)
    stores = ["iOS", "Android"] if a.store == "both" else (["iOS"] if a.store == "ios" else ["Android"])
    if "iOS" in stores:
        ios_checks(root, deps, dfiles)
    if "Android" in stores:
        android_checks(root, deps)
    shared_checks(root, deps, dfiles, stores)
    counts = write_report(root, Path(a.out), stores)
    print(f"Project: {root}\nDependencies: {len(deps)} | Dart files: {len(dfiles)}")
    print("  ".join(f"{ICON[s]} {s}: {n}" for s, n in counts.items()))
    print(f"Report: {Path(a.out) / 'report.md'}")


if __name__ == "__main__":
    main()
