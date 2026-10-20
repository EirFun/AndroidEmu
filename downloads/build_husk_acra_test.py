#!/usr/bin/env python3
"""Build test v4: read AnkiDroid's crash-report preference as 'never'.

Requires build_husk_login_test.py beside this file, Python with androguard 4.1.4,
Java, and baksmali/smali 2.5.2 plus dependencies. Native executables are unchanged.
"""
import argparse
import copy
import json
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import zipfile
from build_husk_login_test import FRAMEWORK, PLIST, methods, require, sha256

V3_SHA256 = 'b0c08130574109f1a173a95d4cbb850a96e8e71f33f92f32a5b06b546e1ac716'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v3_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v3_ipa.read_bytes()) == V3_SHA256, 'Wrong v3 IPA')
    with zipfile.ZipFile(args.v3_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / 'v3.dex'
        source.write_bytes(original.read(FRAMEWORK))
        smali = root / 'smali'
        subprocess.run(['java', '-cp', args.smali_classpath, 'org.jf.baksmali.Main',
                        'disassemble', str(source), '-o', str(smali)], check=True)
        prefs = smali / 'android/content/HuskSharedPreferences.smali'
        text = prefs.read_text()
        pattern = r'(?ms)^\.method public declared-synchronized getString\(Ljava/lang/String;Ljava/lang/String;\)Ljava/lang/String;\n.*?^\.end method'
        match = re.findall(pattern, text)
        require(len(match) == 1, 'Unexpected string getter')
        method = match[0]
        require('    .registers 5' in method, 'Unexpected local registers')
        require(method.count('    monitor-enter p0') == 1, 'Unexpected monitor')
        prefix = '''    const-string v0, "reportErrorMode"
    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :normal_report_preference
    const-string v0, "com.ichi2.anki"
    invoke-static {}, Lhusk/Native;->packageName()Ljava/lang/String;
    move-result-object v1
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :normal_report_preference
    const-string v0, "1"
    return-object v0
    :normal_report_preference
    monitor-enter p0'''
        prefs.write_text(text.replace(method, method.replace('    monitor-enter p0', prefix)))
        dex_file = root / 'v4.dex'
        subprocess.run(['java', '-Xmx2g', '-cp', args.smali_classpath, 'org.jf.smali.Main',
                        'assemble', str(smali), '-o', str(dex_file)], check=True)
        patched = dex_file.read_bytes()
        before, after = methods(source.read_bytes()), methods(patched)
        require(before.keys() == after.keys(), 'Method membership changed')
        changed = [key for key in before if before[key] != after[key]]
        require(len(changed) == 1 and changed[0][:2] == ('Landroid/content/HuskSharedPreferences;', 'getString'),
                'Unexpected semantic method changes: ' + repr(changed[:20]))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v4'
        info['HuskLocalPatch'] += '; read AnkiDroid reportErrorMode as never'
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
                            'Unexpected entry changed: ' + entry.filename)
    report = dict(v3_ipa_sha256=V3_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  changed_existing_methods=changed,
                  validation='Only string preference getter semantically changed relative to v3; other methods and IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False,
                  acra_workaround_device_verified=False, native_socket_crash_fixed=False,
                  override='reportErrorMode reads 1 for com.ichi2.anki, including missing keys; saved reporting choice is not replaced')
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
