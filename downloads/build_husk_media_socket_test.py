#!/usr/bin/env python3
"""Build v10 from pinned v9: image fallback plus bundled libcore socket-family compatibility.

Requires v9 builder/semantic comparator, androguard, smali/baksmali and Java.
The compiled DEX must contain production WebView and AnkiMediaFiles classes.
The native C SO_DOMAIN fix is source-only; no native executable is rebuilt here.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
import zlib
from build_husk_login_test import FRAMEWORK, PLIST, require, sha256
from build_husk_listener_images_test import methods
from androguard.core.dex import DEX

V9_SHA256 = '49b7f961dde231268f7742fa12c9d8b42ebca98d58fda87049bfdb5c0673f32e'
CORE = 'Payload/Husk.app/java-runtime/com.android.art/javalib/core-libart.jar'


def refresh(data):
    data = bytearray(data)
    data[12:32] = hashlib.sha1(data[32:]).digest()
    struct.pack_into('<I', data, 8, zlib.adler32(data[12:]) & 0xffffffff)
    return bytes(data)


def map_entries(data):
    offset = struct.unpack_from('<I', data, 52)[0]
    count = struct.unpack_from('<I', data, offset)[0]
    return offset, [struct.unpack_from('<HHII', data, offset + 4 + i * 12) for i in range(count)]


def without_hidden(data):
    # The tools predate this Android hidden-API flag version. Hide only the map
    # entry for processing; preserve the original metadata bytes for restoration.
    offset, entries = map_entries(data)
    hidden = [item for item in entries if item[0] == 0xf000]
    require(len(hidden) == 1, 'Expected one hidden-API metadata item')
    position = hidden[0][3]
    size = struct.unpack_from('<I', data, position)[0]
    metadata = data[position:position + size]
    require(len(metadata) == size, 'Truncated hidden-API metadata')
    kept = [item for item in entries if item[0] != 0xf000]
    result = bytearray(data)
    struct.pack_into('<I', result, offset, len(kept))
    result[offset + 4:offset + 4 + len(entries) * 12] = b''.join(struct.pack('<HHII', *item) for item in kept) + bytes(12)
    return refresh(result), metadata


def restore_hidden(data, metadata):
    _, entries = map_entries(data)
    require(not any(item[0] == 0xf000 for item in entries), 'Assembler unexpectedly wrote hidden metadata')
    result = bytearray(data)
    result.extend(bytes((-len(result)) % 4))
    hidden_offset = len(result)
    result.extend(metadata)
    result.extend(bytes((-len(result)) % 4))
    map_offset = len(result)
    entries = [(kind, unused, count, map_offset if kind == 0x1000 else offset)
               for kind, unused, count, offset in entries]
    entries.append((0xf000, 0, 1, hidden_offset))
    entries.sort(key=lambda item: item[3])
    result.extend(struct.pack('<I', len(entries)))
    result.extend(b''.join(struct.pack('<HHII', *item) for item in entries))
    struct.pack_into('<I', result, 32, len(result))
    struct.pack_into('<I', result, 52, map_offset)
    data_offset = struct.unpack_from('<I', result, 108)[0]
    struct.pack_into('<I', result, 104, len(result) - data_offset)
    return refresh(result)


def shape(data):
    return [(cls.get_name(),
             [(f.get_name(), f.get_descriptor(), f.get_access_flags()) for f in cls.get_fields()],
             [(m.get_name(), m.get_descriptor(), m.get_access_flags()) for m in cls.get_methods()])
            for cls in DEX(data).get_classes()]


def method_block(text, descriptor):
    pattern = r'(?ms)^\.method [^\n]* ' + re.escape(descriptor) + r'\n.*?^\.end method'
    matches = re.findall(pattern, text)
    require(len(matches) == 1, 'Missing/ambiguous method: ' + descriptor)
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('v9_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    parser.add_argument('--compiled-dex', type=Path, required=True)
    parser.add_argument('--smali-classpath', required=True)
    args = parser.parse_args()
    require(not args.output_ipa.exists(), 'Choose a new output filename')
    require(sha256(args.v9_ipa.read_bytes()) == V9_SHA256, 'Wrong v9 IPA')
    with zipfile.ZipFile(args.v9_ipa) as original, tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / 'framework.dex'; source.write_bytes(original.read(FRAMEWORK))
        jar_bytes = original.read(CORE)
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar:
            core_original = jar.read('classes.dex')
        core_visible, hidden = without_hidden(core_original)
        core_source = root / 'core.dex'; core_source.write_bytes(core_visible)
        smali, helper, core_smali = root/'smali', root/'compiled', root/'core-smali'
        for dex, output in [(source, smali), (args.compiled_dex, helper), (core_source, core_smali)]:
            subprocess.run(['java','-cp',args.smali_classpath,'org.jf.baksmali.Main','disassemble',str(dex),'-o',str(output)], check=True)
        shutil.copy2(helper/'husk/AnkiMediaFiles.smali', smali/'husk/AnkiMediaFiles.smali')
        descriptor = 'serve(ILjava/lang/String;Ljava/lang/String;ZLjava/util/Map;)V'
        web = smali/'android/webkit/WebView.smali'
        old = web.read_text(); new_method = method_block((helper/'android/webkit/WebView.smali').read_text(),descriptor)
        require('ExternalSyntheticLambda' not in new_method, 'Unexpected synthetic dependency')
        web.write_text(old.replace(method_block(old, descriptor),new_method))
        blockguard = core_smali/'libcore/io/BlockGuardOs.smali'
        old = blockguard.read_text()
        replacement = (Path(__file__).resolve().parents[1]/'patches/ankidroid/libcore-isUnixSocket.smali').read_text()
        replacement = replacement[replacement.index('.method'):].strip()
        blockguard.write_text(old.replace(method_block(old,'isUnixSocket(Ljava/io/FileDescriptor;)Z'),replacement))
        patched_framework, patched_core = root/'patched-framework.dex', root/'patched-core.dex'
        for folder, output in [(smali,patched_framework),(core_smali,patched_core)]:
            subprocess.run(['java','-Xmx2g','-cp',args.smali_classpath,'org.jf.smali.Main','assemble','--api','28',str(folder),'-o',str(output)],check=True)
        framework = patched_framework.read_bytes(); core_rebuilt = patched_core.read_bytes()
        before, after = methods(source.read_bytes()), methods(framework)
        require(before.keys() <= after.keys(), 'Removed framework method')
        added = sorted(after.keys()-before.keys())
        require(len(added)==3 and all(key[0]=='Lhusk/AnkiMediaFiles;' for key in added),'Unexpected helper additions: '+repr(added))
        changed = [key for key in before if before[key]!=after[key]]
        require(len(changed)==1 and changed[0][:2]==('Landroid/webkit/WebView;','serve'),'Unexpected framework changes: '+repr(changed))
        require(shape(core_visible)==shape(core_rebuilt),'Core class/member ordering or flags changed; hidden metadata cannot be safely restored')
        before_core, after_core = methods(core_visible), methods(core_rebuilt)
        require(before_core.keys()==after_core.keys(),'Core membership changed')
        core_changed = [key for key in before_core if before_core[key]!=after_core[key]]
        require(len(core_changed)==1 and core_changed[0][:2]==('Llibcore/io/BlockGuardOs;','isUnixSocket'),'Unexpected core changes: '+repr(core_changed))
        core_final = restore_hidden(core_rebuilt,hidden)
        visible_again, restored = without_hidden(core_final)
        require(hidden==restored and methods(visible_again)==after_core,'Hidden metadata restoration changed code/metadata')
        buffer=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar, zipfile.ZipFile(buffer,'w') as output:
            output.comment=jar.comment
            for entry in jar.infolist():
                data=core_final if entry.filename=='classes.dex' else jar.read(entry.filename)
                output.writestr(copy.copy(entry),data)
        patched_jar=buffer.getvalue()
        with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar, zipfile.ZipFile(io.BytesIO(patched_jar)) as output:
            require(output.testzip() is None,'Core JAR integrity failed')
            for entry in jar.infolist():
                if entry.filename!='classes.dex': require(jar.read(entry.filename)==output.read(entry.filename),'Other core JAR entry changed')
        info=plistlib.loads(original.read(PLIST))
        info['HuskBuildCommit']='dbc202a+ankidroid-test-v10'
        info['HuskLocalPatch']+='; media image fallback; libcore socket family via getsockname'
        with zipfile.ZipFile(args.output_ipa,'w') as output:
            output.comment=original.comment
            for entry in original.infolist():
                data=original.read(entry.filename)
                if entry.filename==FRAMEWORK:data=framework
                elif entry.filename==CORE:data=patched_jar
                elif entry.filename==PLIST:data=plistlib.dumps(info,fmt=plistlib.FMT_BINARY)
                output.writestr(copy.copy(entry),data)
        with zipfile.ZipFile(args.output_ipa) as output:
            require(output.testzip() is None,'IPA ZIP integrity failed')
            for entry in original.infolist():
                if entry.filename not in [FRAMEWORK,CORE,PLIST]:
                    require(original.read(entry.filename)==output.read(entry.filename),'Unexpected IPA entry change: '+entry.filename)
    report=dict(v9_ipa_sha256=V9_SHA256,patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                size_bytes=args.output_ipa.stat().st_size,changed_existing_framework_methods=changed,
                added_framework_methods=added,changed_core_methods=core_changed,
                original_hidden_api_metadata_sha256=sha256(hidden),hidden_api_metadata_preserved=True,
                core_class_member_order_and_flags_preserved=True,device_tested=False,
                native_executables_changed=False,native_SO_DOMAIN_source_fix_in_ipa=False,
                libcore_family_compatibility_device_verified=False,image_loading_device_verified=False,
                media_files_copied_or_modified=False,requires_resigning=True,
                validation='One framework method plus image helper; one core method; original hidden-API metadata/order/flags retained; other methods/JAR/IPA entries compared; ZIP checks passed')
    args.output_ipa.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
