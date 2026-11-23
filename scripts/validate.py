"""Fail-closed PortableApps and installer/archive validation."""
import argparse
import configparser
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

APP='OnTheSpotPortable'

def pe(path, require_x64=False):
    p=Path(path)
    if not p.is_file() or p.stat().st_size<1024:raise RuntimeError('PE_MISSING_OR_TOO_SMALL: '+str(path))
    with p.open('rb') as f:
        if f.read(2)!=b'MZ':raise RuntimeError('INVALID_PE_DOS_HEADER: '+str(path))
        f.seek(0x3c);offset=struct.unpack('<I',f.read(4))[0]
        if not 0x40<offset<2*1024*1024:raise RuntimeError('INVALID_PE_OFFSET')
        f.seek(offset)
        if f.read(4)!=b'PE\0\0':raise RuntimeError('INVALID_PE_SIGNATURE: '+str(path))
        machine=struct.unpack('<H',f.read(2))[0]
        if require_x64 and machine!=0x8664:raise RuntimeError('WRONG_PE_ARCH: '+str(path))
    return machine

def validate_stage(root):
    root=Path(root)
    required=['OnTheSpotPortable.exe','help.html','App/AppInfo/appinfo.ini','App/AppInfo/appicon.ico',
              'App/AppInfo/appicon_16.png','App/AppInfo/appicon_32.png',
              'App/OnTheSpot/portable_bootstrap.py','App/OnTheSpot/runtime/python.exe',
              'App/OnTheSpot/runtime/Lib/site-packages/uvicorn',
              'App/OnTheSpot/code/onthespot/otsconfig.py',
              'App/OnTheSpot/ui/index.html',
              'App/OnTheSpot/tools/ffmpeg.exe','App/OnTheSpot/tools/ffprobe.exe',
              'App/OnTheSpot/tools/deno.exe','Other/Source/BUILD-IDENTITY.json',
              'Other/Source/RUNTIME-TOOLS.json', 'Other/Source/ONTHESPOT-GPL-2.0.txt']
    absent=[x for x in required if not (root/x).exists()]
    if absent:raise RuntimeError('STAGE_MISSING: '+', '.join(absent))
    if not (root/'Data').is_dir() or not (root/'App/DefaultData').is_dir():
        raise RuntimeError('PORTABLE_DATA_LAYOUT_INVALID')
    if any((root/'Data').rglob('*')):raise RuntimeError('STAGE_CONTAINS_USER_DATA: refuse distribution')
    pe(root/'OnTheSpotPortable.exe',True)
    pe(root/'App/OnTheSpot/runtime/python.exe',True)
    for x in ('ffmpeg.exe','ffprobe.exe','deno.exe'):pe(root/'App/OnTheSpot/tools'/x,True)
    html=(root/'help.html').read_text(encoding='utf-8')
    if not re.search(r'(?is)<(?:!doctype\s+html|html\b)',html) or '<body' not in html.lower():
        raise RuntimeError('OFFICIAL_HELP_INVALID')
    metadata=configparser.ConfigParser(interpolation=None)
    metadata.read(root/'App/AppInfo/appinfo.ini',encoding='utf-8')
    for section in ('Format','Details','Version','Control'):
        if section not in metadata:raise RuntimeError('PAF_METADATA_MISSING '+section)
    if metadata['Details'].get('AppID')!=APP:raise RuntimeError('PAF_APP_ID_CHANGED')
    if metadata['Control'].get('Start')!='OnTheSpotPortable.exe':raise RuntimeError('PAF_LAUNCHER_INVALID')
    identity=json.loads((root/'Other/Source/BUILD-IDENTITY.json').read_text(encoding='utf-8'))
    if not re.fullmatch(r'v?\d+\.\d+\.\d+',identity['upstream_version']):
        raise RuntimeError('IDENTITY_HAS_UNSTABLE_VERSION')
    if not identity.get('upstream_commit') or len(identity['upstream_commit'])!=40:
        raise RuntimeError('IDENTITY_COMMIT_INVALID')
    if len(list((root/'App/OnTheSpot/runtime/Lib/site-packages').rglob('*.pyd')))==0:
        raise RuntimeError('PYTHON_NATIVE_DEPENDENCIES_MISSING')
    if any((root/'App/OnTheSpot').rglob('*.lnk')):
        raise RuntimeError('UNEXPECTED_WINDOWS_SHORTCUT_IN_BUNDLE')
    print('STATIC_STAGE_VALID:',root, identity['upstream_version'])
    return identity

def extract_zip(path,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('ZIP_CRC_FAILED: '+bad)
        for info in z.infolist():
            name=info.filename.replace('\\','/')
            parts=Path(name).parts
            if not parts or parts[0]!=APP or '..' in parts or name.startswith('/') or ':' in name:
                raise RuntimeError('UNSAFE_ZIP_ENTRY: '+name)
            # symlink file mode: never unzip into Windows directory.
            if ((info.external_attr>>16)&0o170000)==0o120000:
                raise RuntimeError('ZIP_SYMLINK_REJECTED')
        z.extractall(out)
    return out/APP

def validate_zip(path):
    import tempfile
    with tempfile.TemporaryDirectory(prefix='ots-validate-') as temp:
        root=extract_zip(path,temp)
        return validate_stage(root)

def verify_sha(path, manifest):
    text=Path(manifest).read_text(encoding='utf-8-sig')
    entries={}
    for line in text.splitlines():
        m=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)',line.strip())
        if not m:raise RuntimeError('SHA256_MANIFEST_INVALID')
        entries[m.group(2)]=m.group(1).lower()
    if Path(path).name not in entries:raise RuntimeError('ZIP_CHECKSUM_NOT_IN_MANIFEST')
    h=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if entries[Path(path).name]!=h:raise RuntimeError('ZIP_CHECKSUM_MISMATCH')
    print('ZIP_SHA256_VERIFIED',h)

def validate_installer(path,expected_engine,stage):
    pe(path)
    file=Path(path)
    if not file.name.endswith('.paf.exe'):raise RuntimeError('INSTALLER_EXTENSION_INVALID')
    sidecar=Path(str(path)+'.json')
    if not sidecar.is_file():raise RuntimeError('INSTALLER_PROVENANCE_MISSING')
    d=json.loads(sidecar.read_text(encoding='utf-8-sig'))
    if d.get('engine')!=expected_engine:raise RuntimeError('INSTALLER_ENGINE_MISMATCH')
    if d.get('app_id')!='OnTheSpotPortable':raise RuntimeError('INSTALLER_APP_ID_MISMATCH')
    checksum=hashlib.sha256(file.read_bytes()).hexdigest()
    if checksum!=d['sha256']:raise RuntimeError('INSTALLER_CHECKSUM_MISMATCH')
    # The shared action itself asserts seven-zip archive content. This is an
    # independent identity and PE/provenance check, not a claim of install success.
    info=validate_stage(stage)
    if d.get('version') != '.'.join(re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',info['upstream_version']).groups())+'.0':
        raise RuntimeError('INSTALLER_APP_VERSION_MISMATCH')
    print('INSTALLER_STATIC_VALID', expected_engine,file,checksum)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['stage','zip','installer','extract','verify-sha'])
    p.add_argument('--stage',default='build/staging/OnTheSpotPortable')
    p.add_argument('--zip',default='');p.add_argument('--out',default='build/recovered')
    p.add_argument('--manifest',default='');p.add_argument('--installer',default='')
    p.add_argument('--engine',default='custom-nsis')
    args=p.parse_args()
    if args.command=='stage':validate_stage(args.stage)
    elif args.command=='zip':validate_zip(args.zip)
    elif args.command=='extract':
        root=extract_zip(args.zip,args.out);validate_stage(root)
        if os.environ.get('GITHUB_OUTPUT'):
            info=json.loads((root/'Other/Source/BUILD-IDENTITY.json').read_text(encoding='utf-8'))
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
                f.write('staging='+str(root.resolve())+'\n')
                f.write('upstream-version='+info['upstream_version']+'\n')
    elif args.command=='verify-sha':verify_sha(args.zip,args.manifest)
    elif args.command=='installer':validate_installer(args.installer,args.engine,args.stage)
if __name__=='__main__':
    try:main()
    except Exception as e:print('PORTABLE_VALIDATION_FAILED:',e,file=sys.stderr);sys.exit(1)
