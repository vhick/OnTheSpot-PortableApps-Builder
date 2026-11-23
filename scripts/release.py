#!/usr/bin/env python3
"""Fail-closed stable-release discovery, upstream compatibility and build identity."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

REPOSITORY = 'ots-downloader/onthespot'
STABLE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')


def request_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'OnTheSpot-PortableApps-Builder',
                        'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28'})
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)


def stable_release(version=None):
    # Explicit version must still correspond to a published, non-prerelease release.
    releases = []
    for page in range(1, 4):
        chunk = request_json(f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100&page={page}')
        if not isinstance(chunk, list):
            raise RuntimeError('GitHub releases API returned unexpected data')
        releases.extend(chunk)
        if len(chunk) < 100:
            break
    valid = [r for r in releases if STABLE.fullmatch(r.get('tag_name', ''))
             and not r.get('draft') and not r.get('prerelease')
             and int(STABLE.fullmatch(r['tag_name']).group(1)) >= 2]
    if version:
        valid = [r for r in valid if r['tag_name'] == version or r['tag_name'].lstrip('v') == version.lstrip('v')]
    if not valid:
        raise RuntimeError('NO_COMPATIBLE_STABLE_RELEASE: v2+ FastAPI release not found; legacy v1 is intentionally excluded')
    valid.sort(key=lambda r: tuple(map(int, STABLE.fullmatch(r['tag_name']).groups())), reverse=True)
    return valid[0]


def inspect_source(root):
    root = Path(root)
    required = ['api/pyproject.toml','api/uv.lock','api/src/onthespot/main.py',
                'api/src/onthespot/otsconfig.py','api/src/onthespot/otsconfig_default.json',
                'ui/package.json','ui/package-lock.json','Dockerfile','LICENSE']
    absent = [x for x in required if not (root / x).is_file()]
    if absent:
        raise RuntimeError('UPSTREAM_LAYOUT_CHANGED: missing ' + ', '.join(absent))
    pyproject = tomllib.loads((root/'api/pyproject.toml').read_text(encoding='utf-8'))
    if pyproject.get('project',{}).get('name') != 'onthespot':
        raise RuntimeError('UPSTREAM_PROJECT_CHANGED: expected OnTheSpot API project')
    python_min = pyproject['project'].get('requires-python', '')
    match = re.search(r'>=\s*(3\.\d+)', python_min)
    if not match:
        raise RuntimeError('PYTHON_REQUIREMENT_CHANGED: please review Python compatibility: '+python_min)
    python_version = match.group(1)
    if python_version not in ('3.12', '3.13', '3.14'):
        raise RuntimeError('PYTHON_VERSION_UNTESTED: '+python_version)
    dockerfile=(root/'Dockerfile').read_text(encoding='utf-8')
    node = re.search(r'node:(\d+)[-\w]*\s+AS\s+ui-builder', dockerfile, re.I)
    if not node or int(node.group(1)) not in (22,24):
        raise RuntimeError('NODE_VERSION_UNTESTED: expected verified Node 22/24 Docker build')
    uv = re.search(r'ghcr\.io/astral-sh/uv:(\d+\.\d+\.\d+)', dockerfile)
    if not uv:
        raise RuntimeError('UV_VERSION_UNDISCOVERED: upstream Dockerfile changed')
    main = (root/'api/src/onthespot/main.py').read_text(encoding='utf-8')
    cfg=(root/'api/src/onthespot/otsconfig.py').read_text(encoding='utf-8')
    for symbol in ('ONTHESPOT_WEBUI_DIST','StaticFiles(', 'uvicorn'):
        if symbol not in main:
            raise RuntimeError('UPSTREAM_API_CHANGED: '+symbol)
    for symbol in ('ONTHESPOTDIR','ONTHESPOTCACHEDIR','audio_download_path','video_download_path'):
        if symbol not in cfg:
            raise RuntimeError('UPSTREAM_PORTABILITY_CHANGED: '+symbol)
    default=json.loads((root/'api/src/onthespot/otsconfig_default.json').read_text(encoding='utf-8'))
    for key in ('audio_download_path', 'video_download_path', 'download_profiles'):
        if key not in default:
            raise RuntimeError('UPSTREAM_CONFIG_CHANGED: '+key)
    if not (root/'ui/package-lock.json').is_file():
        raise RuntimeError('UPSTREAM_NPM_LOCK_MISSING')
    return {'python_version':python_version, 'node_major':node.group(1),
            'uv_version':uv.group(1), 'embedded_app_version': pyproject['project'].get('version'),
            'embedded_config_version':default.get('version')}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(root, tag, commit, release_url):
    meta = inspect_source(root)
    meta.update({'upstream_repo':REPOSITORY, 'upstream_version':tag,
                 'upstream_commit': commit, 'upstream_release_url':release_url,
                 'builder_revision':'b1r4',
                 'upstream_py_lock_sha256':sha256(Path(root)/'api/uv.lock'),
                 'upstream_npm_lock_sha256':sha256(Path(root)/'ui/package-lock.json'),
                 'installer_package_builder_commit':'9bf686ec29a46073ca3c27638e62862eb8cc9079',
                 'publisher_commit':'cb64f86ac2d8c67506db5832de07f9ff58cbeaeb'})
    return meta


def main():
    p=argparse.ArgumentParser()
    p.add_argument('command', choices=['resolve','inspect'])
    p.add_argument('--version', default='')
    p.add_argument('--source', default='upstream')
    p.add_argument('--out', default='build/identity.json')
    args=p.parse_args()
    if args.command == 'resolve':
        r=stable_release(args.version or None)
        tag=r['tag_name']
        print('Resolved stable upstream:',tag, 'release ID:', r['id'])
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
                f.write('upstream_tag='+tag+'\n')
    else:
        commit=subprocess.check_output(['git','-C',args.source,'rev-parse','HEAD'],text=True).strip()
        tag=args.version.strip()
        if not tag:
            tag=subprocess.check_output(['git','-C',args.source,'describe','--tags','--exact-match'],text=True).strip()
        if not STABLE.fullmatch(tag) or int(STABLE.fullmatch(tag).group(1))<2:
            raise RuntimeError('UPSTREAM_TAG_CHANGED: not a stable v2+ release')
        r=stable_release(tag)
        # A shallow actions/checkout of a tag may omit local tag references.
        # Compare HEAD to the authoritative GitHub commit for this release tag.
        remote=request_json(f'https://api.github.com/repos/{REPOSITORY}/commits/{tag}')
        if remote.get('sha') != commit:
            raise RuntimeError('UPSTREAM_CHECKOUT_COMMIT_MISMATCH: local HEAD differs from published release tag')
        result=identity(args.source,tag,commit,r['html_url'])
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
                for key in ('python_version','node_major','uv_version','upstream_version'):
                    f.write(key+'='+str(result[key])+'\n')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'RELEASE_PRECHECK_FAILED: {exc}',file=sys.stderr);sys.exit(1)
