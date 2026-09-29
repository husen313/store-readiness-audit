#!/usr/bin/env python3
"""
Regression tests for scan_app.py.

Builds two synthetic Flutter projects and checks the scanner's verdicts:
  - trap:  code designed to fool a naive scanner (comments, look-alike
           identifiers, links on the wrong screen, plugin-added permissions).
           Every check must NOT pass.
  - clean: a compliant project. Every check must pass.

Run:  python3 tests/run_tests.py
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCANNER = HERE.parent / "skills" / "store-readiness-audit" / "scripts" / "scan_app.py"
FIX = HERE / "_fixtures"
OUT = HERE / "_out"

sys.path.insert(0, str(SCANNER.parent))
from scan_app import strip_dart_comments  # noqa: E402

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

PUBSPEC = """name: app
version: 1.0.0+1
dependencies:
  flutter:
    sdk: flutter
  firebase_auth: ^5.0.0
  in_app_purchase: ^3.0.0
  google_generative_ai: ^0.4.0
"""


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def base(root):
    if root.exists():
        shutil.rmtree(root)
    w(root / "pubspec.yaml", PUBSPEC)
    w(root / "ios/Runner/Info.plist", '<plist version="1.0"><dict></dict></plist>')
    w(root / "ios/Runner.xcodeproj/project.pbxproj", "PRODUCT_BUNDLE_IDENTIFIER = com.acme.app;")
    w(root / "android/app/build.gradle.kts",
      'android {\n defaultConfig { applicationId = "com.acme.app"\n targetSdk = 36 }\n}\n')


def merged_manifest(root, perms):
    lock = root / "pubspec.lock"
    w(lock, "")
    old = time.time() - 60
    os.utime(lock, (old, old))  # lock older than manifest => manifest is fresh
    body = "".join(f'<uses-permission android:name="android.permission.{p}"/>' for p in perms)
    w(root / "build/app/intermediates/merged_manifests/release/processReleaseManifest/AndroidManifest.xml",
      f"<manifest>{body}<application/></manifest>")


def build_trap(root):
    base(root)
    w(root / "lib/screens/auth.dart", """
Future signup() => FirebaseAuth.instance.createUserWithEmailAndPassword(email: e, password: p);
// TODO: user.delete() for account deletion
""")
    w(root / "lib/screens/paywall_screen.dart", """
class PaywallScreen extends StatelessWidget {
  Widget build(BuildContext c) => Column(children: [Text('Pro monthly subscription')]);
  // restorePurchases() later
  /* privacy policy link here */
}
""")
    w(root / "lib/screens/settings.dart", """
class Settings extends StatelessWidget {
  Widget build(BuildContext c) => ListTile(title: Text('Terms of Use'));
  void x() { FirebaseCrashlytics.instance.reportError(e); final privacyPolicyEnabled = true; }
}
""")
    w(root / "android/app/src/main/AndroidManifest.xml", "<manifest><application/></manifest>")
    merged_manifest(root, ["INTERNET", "READ_MEDIA_IMAGES"])  # added by a plugin


def build_clean(root):
    base(root)
    w(root / "lib/screens/auth.dart", """
Future signup() => FirebaseAuth.instance.createUserWithEmailAndPassword(email: e, password: p);
Future deleteAccount() async { await api.purge(); await FirebaseAuth.instance.currentUser!.delete(); }
final ok = prefs.getBool("aiConsent");
""")
    w(root / "lib/screens/paywall_screen.dart", """
import 'package:in_app_purchase/in_app_purchase.dart';
class PaywallScreen extends StatelessWidget {
  Widget build(BuildContext c) => Column(children: [
    Text('Pro monthly subscription'),
    TextButton(onPressed: () => InAppPurchase.instance.restorePurchases(), child: Text(l10n.restorePurchases)),
    TextButton(onPressed: () => launchUrl(Uri.parse('https://acme.dev/terms')), child: Text('Terms of Use')),
    TextButton(onPressed: () => launchUrl(Uri.parse('https://acme.dev/privacy')), child: Text('Privacy Policy')),
  ]);
}
""")
    w(root / "lib/screens/settings.dart", """
class Settings extends StatelessWidget {
  Widget build(BuildContext c) => Column(children: [
    ListTile(title: Text(l10n.deleteAccountLabel), onTap: deleteAccount),
    IconButton(icon: Icon(Icons.flag), tooltip: 'Report this caption', onPressed: () => reportContent(id)),
  ]);
}
""")
    w(root / "lib/l10n/app_en.arb",
      '{"deleteAccountLabel": "Delete my account", '
      '"aiNotice": "Your text is sent to Google Gemini AI provider to generate captions."}')
    w(root / "android/app/src/main/AndroidManifest.xml", "<manifest><application/></manifest>")
    merged_manifest(root, ["INTERNET"])
    if HAS_PIL:
        icon_dir = root / "ios/Runner/Assets.xcassets/AppIcon.appiconset"
        icon_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 1024), (200, 40, 40)).save(icon_dir / "Icon-App-1024x1024@1x.png")
        mip = root / "android/app/src/main/res/mipmap-xxxhdpi"
        mip.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (192, 192), (200, 40, 40)).save(mip / "ic_launcher.png")


def scan(root, name):
    out = OUT / name
    subprocess.run([sys.executable, str(SCANNER), str(root), "--out", str(out)],
                   check=True, capture_output=True)
    return {r["id"]: r for r in json.loads((out / "report.json").read_text())}


def expect(results, expected, label):
    failures = 0
    for cid, want in expected.items():
        got = results.get(cid, {}).get("status", "missing")
        ok = got == want
        failures += not ok
        print(f"  {'✅' if ok else '❌'} {label} {cid}: expected {want}, got {got}")
    return failures


def test_stripper():
    src = '''a = "https://x.com/privacy"; // restorePurchases()
/* outer /* nested */ still comment restorePurchases() */ b = 'it\\'s // not comment';
c = r'C:\\path'; // gone
d = """multi
// inside triple string
""";'''
    out = strip_dart_comments(src)
    checks = {
        "comment removed": "restorePurchases" not in out,
        "URL in string kept": "https://x.com/privacy" in out,
        "// inside string kept": "// not comment" in out,
        "triple-quoted string kept": "// inside triple" in out,
        "raw string handled": "gone" not in out,
        "line count preserved": src.count("\n") == out.count("\n"),
    }
    fails = 0
    for name, ok in checks.items():
        fails += not ok
        print(f"  {'✅' if ok else '❌'} stripper: {name}")
    return fails


def main():
    FIX.mkdir(exist_ok=True)
    fails = 0
    print("Comment stripper")
    fails += test_stripper()

    print("Trap project (nothing may pass)")
    build_trap(FIX / "trap")
    fails += expect(scan(FIX / "trap", "trap"), {
        "GEN-010": "FAIL", "GEN-011": "WARN", "GEN-020": "FAIL", "GEN-021": "FAIL",
        "GEN-030": "WARN", "GEN-031": "WARN", "AND-010": "WARN",
    }, "trap")

    print("Clean project (everything passes)")
    build_clean(FIX / "clean")
    exp = {"GEN-010": "PASS", "GEN-011": "PASS", "GEN-020": "PASS", "GEN-021": "PASS",
           "GEN-030": "MANUAL", "GEN-031": "PASS", "AND-010": "PASS"}
    if HAS_PIL:
        exp.update({"IOS-031": "PASS", "AND-020": "PASS"})
    fails += expect(scan(FIX / "clean", "clean"), exp, "clean")

    print("HTML report")
    html = (OUT / "trap" / "report.html").read_text()
    ok = "/*__REPORT_DATA__*/null" not in html and '"id": "GEN-020"' in html and "</script" not in html.split("const DATA")[1].split("\n")[0]
    fails += not ok
    print(f"  {'✅' if ok else '❌'} report.html has the scan data embedded")

    print(f"\n{'ALL TESTS PASSED' if not fails else f'{fails} TEST(S) FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
