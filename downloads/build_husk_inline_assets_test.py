#!/usr/bin/env python3
"""Build test v6: inline known AnkiDroid reviewer assets and log initialization.

Compile husk.AnkiReviewerAssets and use D8 --min-api 26 to supply --helper-dex.
Requires build_husk_login_test.py, androguard 4.1.4, Java and smali/baksmali 2.5.2.
"""
import argparse
import copy
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from build_husk_login_test import FRAMEWORK, PLIST, methods, require, sha256

V5_SHA256 = '6ac90e635143298cda1e3e41c493728c4be51fc487ff1ef49cc1b2d42c3837dd'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v5_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--helper-dex', type=Path, required=True)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v5_ipa.read_bytes()) == V5_SHA256, 'Wrong v5 IPA')
    with zipfile.ZipFile(args.v5_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / 'v5.dex'
        source.write_bytes(original.read(FRAMEWORK))
        smali = root / 'smali'
        helper = root / 'helper'
        for dex, output in [(source, smali), (args.helper_dex, helper)]:
            subprocess.run(['java', '-cp', args.smali_classpath, 'org.jf.baksmali.Main',
                            'disassemble', str(dex), '-o', str(output)], check=True)
        helper_files = list(helper.rglob('*.smali'))
        require(len(helper_files) == 1 and helper_files[0].name == 'AnkiReviewerAssets.smali',
                'Helper DEX must contain only AnkiReviewerAssets')
        shutil.copy2(helper_files[0], smali / 'husk/AnkiReviewerAssets.smali')
        webview = smali / 'android/webkit/WebView.smali'
        text = webview.read_text()
        pattern = r'(?ms)^\.method public loadDataWithBaseURL\(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;\)V\n.*?^\.end method'
        matches = re.findall(pattern, text)
        require(len(matches) == 1, 'Unexpected WebView load method')
        method = matches[0]
        old = 'Lhusk/HtmlResourceUrls;->rewrite(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'
        new = 'Lhusk/AnkiReviewerAssets;->prepare(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;'
        require(method.count(old) == 1, 'Expected v5 URL rewrite call')
        replacement = method.replace(old, new)
        webview.write_text(text.replace(method, replacement))
        output_dex = root / 'v6.dex'
        subprocess.run(['java', '-Xmx2g', '-cp', args.smali_classpath, 'org.jf.smali.Main',
                        'assemble', str(smali), '-o', str(output_dex)], check=True)
        patched = output_dex.read_bytes()
        before, after = methods(source.read_bytes()), methods(patched)
        require(before.keys() <= after.keys(), 'An existing method was removed')
        added = sorted(after.keys() - before.keys())
        require(len(added) == 6 and all(k[0] == 'Lhusk/AnkiReviewerAssets;' for k in added),
                'Unexpected added helper methods: ' + repr(added))
        changed = [key for key in before if before[key] != after[key]]
        require(len(changed) == 1 and changed[0][:2] == ('Landroid/webkit/WebView;', 'loadDataWithBaseURL'),
                'Unexpected existing method changes: ' + repr(changed[:20]))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v6'
        info['HuskLocalPatch'] += '; inline known AnkiDroid reviewer scripts and styles; log readiness'
        with zipfile.ZipFile(args.output_ipa, 'w') as output:
            output.comment = original.comment
            for entry in original.infolist():
                data = original.read(entry.filename)
                if entry.filename == FRAMEWORK:
                    data = patched
                elif entry.filename == PLIST:
                    data = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
                output.writestr(copy.copy(entry), data)
        with zipfile.ZipFile(args.output_ipa) as output:
            require(output.testzip() is None, 'IPA ZIP integrity failed')
            require(output.read(FRAMEWORK) == patched, 'Framework packaging mismatch')
            for entry in original.infolist():
                if entry.filename not in [FRAMEWORK, PLIST]:
                    require(original.read(entry.filename) == output.read(entry.filename),
                            'Unexpected entry change: ' + entry.filename)
    report = dict(v5_ipa_sha256=V5_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  added_framework_methods=added, changed_existing_methods=changed,
                  helper_dex_sha256=sha256(args.helper_dex.read_bytes()),
                  validation='Only WebView.loadDataWithBaseURL and the new compiled AnkiReviewerAssets helper differ from v5; all other existing methods and retained IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False,
                  reviewer_script_loading_device_verified=False,
                  native_socket_crash_fixed=False, pencil_support_fixed=False)
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
