#!/usr/bin/env python3
"""Build test v8: guard NanoHTTPD retries, route reviewer assets and diagnose card DOM.

Compile WebView, AnkiReviewerAssets and AnkiSocketDiagnostics, then D8 into --compiled-dex.
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
from build_husk_login_test import FRAMEWORK, PLIST, require, sha256
from androguard.core.dex import DEX, Operand

V7_SHA256 = 'e0c958cf1844099b512e012b5bff0ca03725d0e24bca320c4f6e7e35d21b230a'


def methods(data):
    # const-string/jumbo widths move branch byte offsets. Compare the same logical
    # branch destination instruction, not its displacement in the encoded method.
    result = {}
    for cls in DEX(data).get_classes():
        for method in cls.get_methods():
            code = list(method.get_instructions())
            offsets, position = {}, 0
            for index, instruction in enumerate(code):
                offsets[position] = index
                position += instruction.get_length()
            normalized, position = [], 0
            for instruction in code:
                name = instruction.get_name()
                operands = instruction.get_operands()
                if name in ('const-string', 'const-string/jumbo'):
                    normalized.append(('const-string', operands[0][1], instruction.get_string()))
                elif name.startswith('if-') or name in ('goto', 'goto/16', 'goto/32'):
                    converted = []
                    for operand in operands:
                        if operand[0] == Operand.OFFSET:
                            destination = position + operand[1] * 2
                            require(destination in offsets, 'Invalid branch target')
                            converted.append(('target-instruction', offsets[destination]))
                        else:
                            converted.append(tuple(operand))
                    normalized.append(('goto' if name.startswith('goto') else name, converted))
                else:
                    normalized.append((name, instruction.get_output()))
                position += instruction.get_length()
            key = (cls.get_name(), method.get_name(), method.get_descriptor())
            result[key] = (method.get_access_flags(), normalized)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v7_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--compiled-dex', type=Path, required=True)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v7_ipa.read_bytes()) == V7_SHA256, 'Wrong v7 IPA')
    with zipfile.ZipFile(args.v7_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / 'v7.dex'
        source.write_bytes(original.read(FRAMEWORK))
        smali = root / 'smali'
        helper = root / 'helper'
        for dex, output in [(source, smali), (args.compiled_dex, helper)]:
            subprocess.run(['java', '-cp', args.smali_classpath, 'org.jf.baksmali.Main',
                            'disassemble', str(dex), '-o', str(output)], check=True)
        for name in ['AnkiReviewerAssets', 'AnkiSocketDiagnostics']:
            helper_file = helper / ('husk/' + name + '.smali')
            require(helper_file.is_file(), 'Missing helper class: ' + name)
            shutil.copy2(helper_file, smali / ('husk/' + name + '.smali'))
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
            'eval(Ljava/lang/String;Landroid/webkit/ValueCallback;)V',
            'serve(ILjava/lang/String;Ljava/lang/String;ZLjava/util/Map;)V',
        ]
        for descriptor in targets:
            require(descriptor in original_methods and descriptor in compiled_methods, 'Missing target: ' + descriptor)
            replacement = compiled_methods[descriptor]
            require('ExternalSyntheticLambda' not in replacement, 'Unexpected synthetic dependency')
            text = text.replace(original_methods[descriptor], replacement)
        webview.write_text(text)
        output_dex = root / 'v8.dex'
        subprocess.run(['java', '-Xmx2g', '-cp', args.smali_classpath, 'org.jf.smali.Main',
                        'assemble', str(smali), '-o', str(output_dex)], check=True)
        patched = output_dex.read_bytes()
        before, after = methods(source.read_bytes()), methods(patched)
        require(before.keys() <= after.keys(), 'An existing method was removed')
        added = sorted(after.keys() - before.keys())
        require(len(added) == 6 and all(k[0] in ['Lhusk/AnkiSocketDiagnostics;', 'Lhusk/AnkiReviewerAssets;'] for k in added),
                'Unexpected added helper methods: ' + repr(added))
        changed = [key for key in before if before[key] != after[key]]
        expected = {('Landroid/webkit/WebView;', 'loadDataWithBaseURL'),
                    ('Landroid/webkit/WebView;', 'eval'), ('Landroid/webkit/WebView;', 'serve'),
                    ('Lhusk/AnkiReviewerAssets;', 'prepare')}
        require(len(changed) == 4 and {key[:2] for key in changed} == expected,
                'Unexpected existing method changes: ' + repr(changed))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v8'
        info['HuskLocalPatch'] += '; bound NanoHTTPD error retries; route reviewer localhost resources; diagnose card DOM'
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
    report = dict(v7_ipa_sha256=V7_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  added_framework_methods=added, changed_existing_methods=changed,
                  compiled_dex_sha256=sha256(args.compiled_dex.read_bytes()),
                  validation='Only four intended existing methods and six helper methods differ from v7; all other existing methods and retained IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False,
                  blank_card_fix_device_verified=False, retry_guard_device_verified=False,
                  native_socket_crash_fixed=False, pencil_tool_type_fixed=False, whiteboard_input_device_verified=False, back_freeze_fixed=False)
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
