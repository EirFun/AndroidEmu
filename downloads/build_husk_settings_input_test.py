#!/usr/bin/env python3
"""Build test v7: apply WebView settings before loads and route Anki whiteboard input.

Compile WebView and AnkiWhiteboardInput, then D8 both class files into --compiled-dex.
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

V6_SHA256 = 'c23acb84f895236e7cdd83abc2f8952ebcc261d9ce41287affaad60a2853b27c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v6_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--compiled-dex', type=Path, required=True)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v6_ipa.read_bytes()) == V6_SHA256, 'Wrong v6 IPA')
    with zipfile.ZipFile(args.v6_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / 'v6.dex'
        source.write_bytes(original.read(FRAMEWORK))
        smali = root / 'smali'
        helper = root / 'helper'
        for dex, output in [(source, smali), (args.compiled_dex, helper)]:
            subprocess.run(['java', '-cp', args.smali_classpath, 'org.jf.baksmali.Main',
                            'disassemble', str(dex), '-o', str(output)], check=True)
        helper_file = helper / 'husk/AnkiWhiteboardInput.smali'
        require(helper_file.is_file(), 'Missing AnkiWhiteboardInput class')
        shutil.copy2(helper_file, smali / 'husk/AnkiWhiteboardInput.smali')
        webview = smali / 'android/webkit/WebView.smali'
        text = webview.read_text()
        compiled = (helper / 'android/webkit/WebView.smali').read_text()
        def find_methods(source):
            found = re.findall(r'(?ms)^\.method ([^\n]+)\n.*?^\.end method', source)
            result = {}
            for signature in found:
                descriptor = signature.split()[-1]
                pattern = r'(?ms)^\.method ' + re.escape(signature) + r'\n.*?^\.end method'
                result[descriptor] = re.search(pattern, source)[0]
            return result
        original_methods, compiled_methods = find_methods(text), find_methods(compiled)
        targets = [
            'loadDataWithBaseURL(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V',
            'loadData(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V',
            'postUrl(Ljava/lang/String;[B)V',
            'updateFrame(Z)V',
            'destroy()V',
        ]
        for descriptor in targets:
            require(descriptor in original_methods and descriptor in compiled_methods, 'Missing target: ' + descriptor)
            replacement = compiled_methods[descriptor]
            require('ExternalSyntheticLambda' not in replacement, 'Unexpected synthetic dependency')
            text = text.replace(original_methods[descriptor], replacement)
        # Keep the packaged load() lambda references exactly as they were: only insert the flush.
        descriptor = 'load(Ljava/lang/String;Ljava/util/Map;)V'
        method = original_methods[descriptor]
        entry = re.search(r'if-nez p1, (:[a-zA-Z_0-9]+)', method)
        require(entry is not None, 'Unexpected URL null guard')
        label = '    ' + entry[1] + '\n'
        require(method.count(label) == 1, 'Unexpected load target label')
        replacement = method.replace(label, label + '    invoke-direct/range {p0 .. p0}, Landroid/webkit/WebView;->pushSettings()V\n')
        text = text.replace(method, replacement)
        webview.write_text(text)
        output_dex = root / 'v7.dex'
        subprocess.run(['java', '-Xmx2g', '-cp', args.smali_classpath, 'org.jf.smali.Main',
                        'assemble', str(smali), '-o', str(output_dex)], check=True)
        patched = output_dex.read_bytes()
        before, after = methods(source.read_bytes()), methods(patched)
        require(before.keys() <= after.keys(), 'An existing method was removed')
        added = sorted(after.keys() - before.keys())
        require(len(added) == 3 and all(k[0] == 'Lhusk/AnkiWhiteboardInput;' for k in added),
                'Unexpected added helper methods: ' + repr(added))
        changed = [key for key in before if before[key] != after[key]]
        expected = {'loadDataWithBaseURL', 'loadData', 'postUrl', 'load', 'updateFrame', 'destroy'}
        require(len(changed) == 6 and {key[1] for key in changed} == expected
                and all(key[0] == 'Landroid/webkit/WebView;' for key in changed),
                'Unexpected existing method changes: ' + repr(changed))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v7'
        info['HuskLocalPatch'] += '; flush WebView settings before navigation; route visible Anki whiteboard input; log frame cleanup'
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
    report = dict(v6_ipa_sha256=V6_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  added_framework_methods=added, changed_existing_methods=changed,
                  compiled_dex_sha256=sha256(args.compiled_dex.read_bytes()),
                  validation='Only six intended WebView methods and the new compiled AnkiWhiteboardInput helper differ from v6; all other existing methods and retained IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False,
                  reviewer_script_loading_device_verified=False,
                  native_socket_crash_fixed=False, pencil_tool_type_fixed=False, whiteboard_input_device_verified=False, back_freeze_fixed=False)
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
