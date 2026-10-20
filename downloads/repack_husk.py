#!/usr/bin/env python3
"""Patch only Application attach order in official Husk 3.0.0 build 129.

Requires Python 3 and androguard==4.1.4. The output IPA requires re-signing
with a sideloader; it is not a native iOS rebuild or a verified login fix.
"""
import argparse
import copy
import hashlib
import json
import plistlib
import struct
import zipfile
import zlib
from pathlib import Path

from loguru import logger
logger.remove()
from androguard.core.dex import DEX

ORIGINAL_IPA_SHA256 = '112a1ddbb3143ae25e80c18c5b195b6dfa5067d66cbf99d2188fc03f4ab0f61d'
ORIGINAL_DEX_SHA256 = 'aadfd5ae8deb861b834aaba94f71a8c9ccf7ca6afb81e61e9bbaa6145954794c'
FRAMEWORK = 'Payload/Husk.app/java-runtime/husk-framework.dex'
PLIST = 'Payload/Husk.app/Info.plist'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def startup_calls(data):
    dex = DEX(data)
    cls = dex.get_class('Lhusk/AppRunner;')
    methods = [m for m in cls.get_methods() if m.get_name() == 'run']
    if len(methods) != 1:
        raise ValueError('Expected exactly one AppRunner.run method')
    method = methods[0]
    offset = 0
    calls = []
    for ins in method.get_instructions():
        output = ins.get_output()
        if ('Lhusk/ContextImpl;->setApplication(' in output
                or 'Landroid/app/Application;->huskAttach(' in output):
            calls.append((offset, bytes(ins.get_raw()), ins.get_name(), output))
        offset += ins.get_length()
    return method, calls


def patch_dex(original):
    if sha256(original) != ORIGINAL_DEX_SHA256:
        raise ValueError('Unrecognized framework: refusing to patch another build')
    if original[12:32] != hashlib.sha1(original[32:]).digest():
        raise ValueError('Invalid original DEX signature')
    if struct.unpack_from('<I', original, 8)[0] != zlib.adler32(original[12:]):
        raise ValueError('Invalid original DEX checksum')
    method, calls = startup_calls(original)
    if len(calls) != 2:
        raise ValueError('Expected exactly two startup calls')
    first, second = calls
    if (first[2] != 'invoke-static' or 'setApplication' not in first[3]
            or second[2] != 'invoke-virtual' or 'huskAttach' not in second[3]
            or len(first[1]) != 6 or len(second[1]) != 6
            or second[0] != first[0] + 6):
        raise ValueError('Unexpected call order, opcodes, size, or adjacency')
    # A DEX code_item has a 16-byte header, then its instruction array.
    position = method.get_code_off() + 16 + first[0]
    if original[position:position + 12] != first[1] + second[1]:
        raise ValueError('Instruction offsets do not match the DEX bytes')
    changed = bytearray(original)
    changed[position:position + 12] = second[1] + first[1]
    changed[12:32] = hashlib.sha1(changed[32:]).digest()
    struct.pack_into('<I', changed, 8, zlib.adler32(changed[12:]))
    changed = bytes(changed)
    _, after = startup_calls(changed)
    if [call[1] for call in after] != [second[1], first[1]]:
        raise ValueError('Reparsed DEX does not have the expected fixed order')
    # Only the two invokes and the DEX integrity fields may differ.
    assert original[32:position] == changed[32:position]
    assert original[position + 12:] == changed[position + 12:]
    assert len(original) == len(changed)
    return changed, {'instruction_file_offset': hex(position),
                     'before': [c[3] for c in calls],
                     'after': [c[3] for c in after]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_ipa', type=Path)
    parser.add_argument('output_ipa', type=Path)
    args = parser.parse_args()
    if args.output_ipa.exists():
        parser.error('Output already exists; choose a new output path')
    if sha256(args.original_ipa.read_bytes()) != ORIGINAL_IPA_SHA256:
        parser.error('Input does not match the inspected official release')
    with zipfile.ZipFile(args.original_ipa) as source:
        if source.testzip() is not None:
            raise ValueError('Original IPA ZIP integrity failed')
        original = source.read(FRAMEWORK)
        patched, report = patch_dex(original)
        info = plistlib.loads(source.read(PLIST))
        assert (info['CFBundleShortVersionString'], info['CFBundleVersion']) == ('3.0.0', '129')
        # Preserve the original release identity and label this local modification.
        info['HuskBuildCommit'] = str(info.get('HuskBuildCommit', 'unknown')) + '+attach-order-fix'
        info['HuskLocalPatch'] = 'Application attach ordering; requires sideloader re-signing'
        removed = []
        with zipfile.ZipFile(args.output_ipa, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            target.comment = source.comment
            for entry in source.infolist():
                name = entry.filename
                # The old app resource seal no longer matches. Embedded executable
                # entitlements remain available to the sideloader for re-signing.
                if name.startswith('Payload/Husk.app/_CodeSignature/'):
                    removed.append(name)
                    continue
                data = patched if name == FRAMEWORK else source.read(name)
                if name == PLIST:
                    data = plistlib.dumps(info, fmt=plistlib.FMT_BINARY)
                target.writestr(copy.copy(entry), data)
        with zipfile.ZipFile(args.output_ipa) as target:
            assert target.testzip() is None
            assert target.read(FRAMEWORK) == patched
            for entry in source.infolist():
                if entry.filename not in removed + [FRAMEWORK, PLIST]:
                    assert source.read(entry.filename) == target.read(entry.filename)
    report.update(original_ipa_sha256=ORIGINAL_IPA_SHA256,
                  patched_ipa_sha256=sha256(args.output_ipa.read_bytes()),
                  original_dex_sha256=sha256(original),
                  patched_dex_sha256=sha256(patched),
                  removed_stale_signature_entries=removed,
                  validation='DEX reparsed; byte changes bounded; every other retained IPA entry compared byte-for-byte; ZIP integrity passed',
                  device_tested=False, login_verified=False, requires_resigning=True)
    report_path = args.output_ipa.with_suffix('.validation.json')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
