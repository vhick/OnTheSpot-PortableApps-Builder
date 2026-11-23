"""Safely collect validated shared-action installer into workspace-relative release paths.

Shared Package Builder compiles in a deliberately short absolute Windows directory,
so NSIS doesn't run into legacy MAX_PATH limitations with deep Python venv trees.
The app builder, not the shared packager, mirrors verified outputs for publishing.
No installer compilation, source modification, or Data operations occur here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def collect(source, destination):
    src=Path(source).resolve(strict=True)
    dest=Path(destination).absolute()
    if not src.is_file() or src.is_symlink() or not src.name.endswith('.paf.exe'):
        raise RuntimeError('INSTALLER_SOURCE_INVALID')
    if src.parent == dest or src.parent in dest.parents or dest in src.parents:
        raise RuntimeError('INSTALLER_MIRROR_PATH_OVERLAP')
    meta_path=Path(str(src)+'.json')
    sum_path=Path(str(src)+'.sha256')
    if not meta_path.is_file() or not sum_path.is_file() or meta_path.is_symlink() or sum_path.is_symlink():
        raise RuntimeError('INSTALLER_SIDECARS_MISSING')
    meta=json.loads(meta_path.read_text(encoding='utf-8-sig'))
    digest=sha256(src)
    text=sum_path.read_text(encoding='ascii').strip()
    match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)', text)
    if not match or match.group(1).lower()!=digest or match.group(2)!=src.name:
        raise RuntimeError('INSTALLER_SHA256_SIDECAR_MISMATCH')
    if meta.get('sha256')!=digest or meta.get('engine') not in ('official','custom-nsis'):
        raise RuntimeError('INSTALLER_PROVENANCE_MISMATCH')
    if Path(str(meta.get('file',''))).resolve()!=src:
        raise RuntimeError('INSTALLER_ORIGIN_PATH_MISMATCH')
    if meta.get('app_id')!='OnTheSpotPortable':
        raise RuntimeError('INSTALLER_APP_ID_MISMATCH')
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/src.name
    targets=(target, Path(str(target)+'.sha256'),Path(str(target)+'.json'))
    if any(p.exists() or p.is_symlink() for p in targets):
        raise RuntimeError('INSTALLER_MIRROR_REFUSES_OVERWRITE')
    try:
        # File bytes and checksum text remain exactly as shared action generated.
        shutil.copy2(src,targets[0]);shutil.copy2(sum_path,targets[1])
        # Provenance retains the original build path and records final distribution path.
        meta['compiler_output_path']=meta['file']
        meta['file']=str(target)
        targets[2].write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        if sha256(target)!=digest or targets[1].read_bytes()!=sum_path.read_bytes():
            raise RuntimeError('INSTALLER_MIRROR_CHECKSUM_FAILED')
    except Exception:
        # Only clean up our new outputs, never touch original source or user data.
        for p in targets:
            if p.is_file():p.unlink()
        raise
    print('INSTALLER_WORKSPACE_COPY_VALID:',target,digest)
    return target


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True)
    ap.add_argument('--destination',default='build/installers')
    args=ap.parse_args()
    target=collect(args.source,args.destination)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as handle:
            handle.write('installer-file='+str(target)+'\n')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('INSTALLER_COLLECT_FAILED:',exc,file=sys.stderr)
        sys.exit(1)
