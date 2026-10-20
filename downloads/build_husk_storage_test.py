#!/usr/bin/env python3
"""Add guarded existing-collection relocation to the verified Husk test-v2 IPA.

Compile src/java-framework/src/husk/AnkiStoragePath.java with the framework,
then use D8 --min-api 26 to turn its class file into the helper DEX supplied here.
Requires build_husk_login_test.py beside this script, androguard 4.1.4,
Java, and baksmali/smali 2.5.2 plus their dependencies.
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

V2_SHA256 = '7c5e1f1f7d976edc22b833b52e532c7316c9d69ac966c3e448c4ff3339684918'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v2_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--helper-dex', type=Path, required=True)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v2_ipa.read_bytes()) == V2_SHA256, 'Wrong test-v2 IPA')
    with zipfile.ZipFile(args.v2_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = directory / 'v2.dex'
        source.write_bytes(original.read(FRAMEWORK))
        smali = directory / 'smali'
        helper_smali = directory / 'helper'
        for dex, output in [(source, smali), (args.helper_dex, helper_smali)]:
            subprocess.run(['java', '-cp', args.smali_classpath, 'org.jf.baksmali.Main',
                            'disassemble', str(dex), '-o', str(output)], check=True)
        helper_files = list(helper_smali.rglob('*.smali'))
        require(len(helper_files) == 1 and helper_files[0].name == 'AnkiStoragePath.smali',
                'Helper DEX must contain only AnkiStoragePath')
        shutil.copy2(helper_files[0], smali / 'husk/AnkiStoragePath.smali')
        prefs = smali / 'android/content/HuskSharedPreferences.smali'
        text = prefs.read_text()
        pattern = r'(?ms)^\.method public declared-synchronized getString\(Ljava/lang/String;Ljava/lang/String;\)Ljava/lang/String;\n.*?^\.end method'
        require(len(re.findall(pattern, text)) == 1, 'Unexpected preference getter')
        replacement = '''.method public declared-synchronized getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    .locals 2
    monitor-enter p0
    :try_start
    iget-object v0, p0, Landroid/content/HuskSharedPreferences;->map:Ljava/util/HashMap;
    invoke-virtual {v0, p1}, Ljava/util/HashMap;->get(Ljava/lang/Object;)Ljava/lang/Object;
    move-result-object v0
    instance-of v1, v0, Ljava/lang/String;
    if-eqz v1, :fallback
    check-cast v0, Ljava/lang/String;
    invoke-static {p1, v0}, Lhusk/AnkiStoragePath;->forPreference(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    goto :done
    :fallback
    move-object v0, p2
    :try_end
    .catchall {:try_start .. :try_end} :failed
    :done
    monitor-exit p0
    return-object v0
    :failed
    move-exception v0
    monitor-exit p0
    throw v0
.end method'''
        prefs.write_text(re.sub(pattern, lambda _: replacement, text))
        output_dex = directory / 'v3.dex'
        subprocess.run(['java', '-Xmx2g', '-cp', args.smali_classpath, 'org.jf.smali.Main',
                        'assemble', str(smali), '-o', str(output_dex)], check=True)
        patched = output_dex.read_bytes()
        before, after = methods(source.read_bytes()), methods(patched)
        require(before.keys() <= after.keys(), 'An existing method was removed')
        added = sorted(after.keys() - before.keys())
        require(len(added) == 3 and all(k[0] == 'Lhusk/AnkiStoragePath;' for k in added),
                'Unexpected added helper methods: ' + repr(added))
        changed = [k for k in before if before[k] != after[k]]
        require(len(changed) == 1 and changed[0][:2] == ('Landroid/content/HuskSharedPreferences;', 'getString'),
                'Unexpected existing method changes: ' + repr(changed[:20]))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v3'
        info['HuskLocalPatch'] += '; guarded existing-collection relocation'
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
            require(output.testzip() is None, 'V3 ZIP integrity failed')
            require(output.read(FRAMEWORK) == patched, 'Packaged framework mismatch')
            for entry in original.infolist():
                if entry.filename not in [FRAMEWORK, PLIST]:
                    require(original.read(entry.filename) == output.read(entry.filename),
                            'Unexpected IPA entry change: ' + entry.filename)
    report = dict(v2_ipa_sha256=V2_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  added_framework_methods=added, changed_existing_methods=changed,
                  helper_dex_sha256=sha256(args.helper_dex.read_bytes()),
                  validation='Relative to v2: only preference string getter changed plus the compiled relocation helper; other methods compared; retained IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False, storage_fix_device_verified=False,
                  login_verified=False, editor_fix_verified=False,
                  saved_preferences_modified=False, collection_files_modified=False)
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
