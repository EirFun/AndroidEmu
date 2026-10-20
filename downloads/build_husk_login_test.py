#!/usr/bin/env python3
"""Build experimental Husk test v2 from the official 3.0 build-129 IPA.

Needs Java, baksmali/smali 2.5.2 and their dependencies on a classpath,
and androguard 4.1.4 for semantic verification. No native iOS build is done.
"""
import argparse
import copy
import difflib
import hashlib
import json
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import zipfile

from loguru import logger
logger.remove()
from androguard.core.dex import DEX

ORIGINAL_SHA256 = '112a1ddbb3143ae25e80c18c5b195b6dfa5067d66cbf99d2188fc03f4ab0f61d'
FRAMEWORK = 'Payload/Husk.app/java-runtime/husk-framework.dex'
PLIST = 'Payload/Husk.app/Info.plist'


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def methods(data):
    result = {}
    for cls in DEX(data).get_classes():
        for m in cls.get_methods():
            key = (cls.get_name(), m.get_name(), m.get_descriptor())
            instructions = []
            for ins in m.get_instructions():
                if ins.get_name() in ('const-string', 'const-string/jumbo'):
                    # New strings may move an existing constant beyond index 65535.
                    # Compare the destination and resolved value, not its index width.
                    instructions.append(('const-string', ins.get_operands()[0][1], ins.get_string()))
                else:
                    instructions.append((ins.get_name(), ins.get_output()))
            result[key] = (m.get_access_flags(), instructions)
    return result


def build_framework(original, classpath, directory):
    source = directory / 'original.dex'
    source.write_bytes(original)
    smali = directory / 'smali'
    subprocess.run(['java', '-cp', classpath, 'org.jf.baksmali.Main',
                    'disassemble', str(source), '-o', str(smali)], check=True)

    app_runner = smali / 'husk/AppRunner.smali'
    text = app_runner.read_text()
    old = ('invoke-static {p1}, Lhusk/ContextImpl;->setApplication(Landroid/content/Context;)V\n'
           '\n    .line 92\n'
           '    invoke-virtual {p1, v0}, Landroid/app/Application;->huskAttach(Landroid/content/Context;)V')
    new = ('invoke-virtual {p1, v0}, Landroid/app/Application;->huskAttach(Landroid/content/Context;)V\n'
           '\n    .line 92\n'
           '    invoke-static {p1}, Lhusk/ContextImpl;->setApplication(Landroid/content/Context;)V')
    require(text.count(old) == 1, 'Unexpected AppRunner startup sequence')
    app_runner.write_text(text.replace(old, new))

    message = smali / 'android/os/Message.smali'
    text = message.read_text()
    pattern = r'(?ms)^\.method public static obtain\(Landroid/os/Message;\)Landroid/os/Message;\n.*?^\.end method'
    require(len(re.findall(pattern, text)) == 1, 'Unexpected Message.obtain method')
    body = ['.method public static obtain(Landroid/os/Message;)Landroid/os/Message;',
            '    .locals 3',
            '    invoke-static {}, Landroid/os/Message;->obtain()Landroid/os/Message;',
            '    move-result-object v0']
    fields = [('what', 'I'), ('arg1', 'I'), ('arg2', 'I'),
              ('obj', 'Ljava/lang/Object;'), ('replyTo', 'Landroid/os/Messenger;'),
              ('sendingUid', 'I'), ('workSourceUid', 'I'),
              ('target', 'Landroid/os/Handler;'), ('callback', 'Ljava/lang/Runnable;')]
    for name, kind in fields:
        suffix = '-object' if kind.startswith('L') else ''
        body += [f'    iget{suffix} v1, p0, Landroid/os/Message;->{name}:{kind}',
                 f'    iput{suffix} v1, v0, Landroid/os/Message;->{name}:{kind}']
    body += ['    iget-object v1, p0, Landroid/os/Message;->data:Landroid/os/Bundle;',
             '    if-eqz v1, :done',
             '    new-instance v2, Landroid/os/Bundle;',
             '    invoke-direct {v2, v1}, Landroid/os/Bundle;-><init>(Landroid/os/Bundle;)V',
             '    iput-object v2, v0, Landroid/os/Message;->data:Landroid/os/Bundle;',
             '    :done', '    return-object v0', '.end method']
    message.write_text(re.sub(pattern, lambda _: '\n'.join(body), text))

    prefs = smali / 'android/content/HuskSharedPreferences.smali'
    text = prefs.read_text()
    pattern = r'(?ms)^\.method public declared-synchronized getBoolean\(Ljava/lang/String;Z\)Z\n.*?^\.end method'
    matches = re.findall(pattern, text)
    require(len(matches) == 1, 'Unexpected SharedPreferences.getBoolean method')
    original_method = matches[0]
    require(original_method.count('    .registers 4') == 1, 'Unexpected preference registers')
    require(original_method.count('    monitor-enter p0') == 1, 'Unexpected preference monitor')
    prefix = '''    const-string v0, "noteEditorShowPreviewer"
    invoke-virtual {v0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :normal_preference
    const-string v0, "com.ichi2.anki"
    invoke-static {}, Lhusk/Native;->packageName()Ljava/lang/String;
    move-result-object v1
    invoke-virtual {v0, v1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :normal_preference
    const/4 v0, 0x0
    return v0
    :normal_preference
    monitor-enter p0'''
    patched_method = original_method.replace('    .registers 4', '    .registers 5')
    patched_method = patched_method.replace('    monitor-enter p0', prefix)
    prefs.write_text(text.replace(original_method, patched_method))

    output = directory / 'patched.dex'
    subprocess.run(['java', '-Xmx2g', '-cp', classpath, 'org.jf.smali.Main',
                    'assemble', str(smali), '-o', str(output)], check=True)
    patched = output.read_bytes()
    before, after = methods(original), methods(patched)
    require(before.keys() == after.keys(), 'Framework class/method membership changed')
    changes = [key for key in before if before[key] != after[key]]
    expected = {('Lhusk/AppRunner;', 'run'),
                ('Landroid/os/Message;', 'obtain'),
                ('Landroid/content/HuskSharedPreferences;', 'getBoolean')}
    for key in changes:
        if (key[0], key[1]) not in expected:
            print('Unexpected method:', key)
            print('\n'.join(difflib.unified_diff(
                [repr(i) for i in before[key][1]], [repr(i) for i in after[key][1]],
                fromfile='original', tofile='assembled')))
    require(len(changes) == 3 and {(c[0], c[1]) for c in changes} == expected,
            'Unexpected semantic method changes: ' + repr(changes[:20]))
    return patched, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.original_ipa.read_bytes()) == ORIGINAL_SHA256, 'Wrong official release')
    with zipfile.ZipFile(args.original_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        require(original.testzip() is None, 'Original ZIP integrity failed')
        patched, changes = build_framework(original.read(FRAMEWORK), args.smali_classpath, Path(tmp))
        info = plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit'] = 'dbc202a+ankidroid-test-v2'
        info['HuskLocalPatch'] = 'Attach order, Message copy, temporary AnkiDroid single-pane override'
        omitted = []
        with zipfile.ZipFile(args.output_ipa, 'w') as output:
            output.comment = original.comment
            for entry in original.infolist():
                if entry.filename.startswith('Payload/Husk.app/_CodeSignature/'):
                    omitted.append(entry.filename)
                    continue
                data = original.read(entry.filename)
                if entry.filename == FRAMEWORK:
                    data = patched
                elif entry.filename == PLIST:
                    data = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
                output.writestr(copy.copy(entry), data)
        with zipfile.ZipFile(args.output_ipa) as output:
            require(output.testzip() is None, 'Patched ZIP integrity failed')
            require(output.read(FRAMEWORK) == patched, 'Packaged framework mismatch')
            for entry in original.infolist():
                if entry.filename not in omitted + [FRAMEWORK, PLIST]:
                    require(original.read(entry.filename) == output.read(entry.filename),
                            'Unexpected IPA change: ' + entry.filename)
    report = dict(original_ipa_sha256=ORIGINAL_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  size_bytes=args.output_ipa.stat().st_size,
                  changed_framework_methods=changes,
                  patched_dex_sha256=sha256(patched),
                  validation='All decoded method instructions compared, normalizing equivalent const-string/jumbo forms; exactly three methods semantically changed; retained IPA entries compared; ZIP integrity passed',
                  requires_resigning=True, device_tested=False, login_verified=False,
                  editor_fix_verified=False,
                  preview_override='Reads false only for noteEditorShowPreviewer in com.ichi2.anki; stored preference unchanged')
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
