"""Fetch trusted upstream runtime tools. Records exact artifact SHA-256 and release URLs.

Only trusted repositories are allowed. Never run archive-contained installation scripts.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

HEADERS={'User-Agent':'OnTheSpot-PortableApps-Builder','Accept':'application/vnd.github+json'}

def json_url(url):
    import os
    req=urllib.request.Request(url,headers=dict(HEADERS))
    if os.getenv('GITHUB_TOKEN'):
        req.add_header('Authorization','Bearer '+os.environ['GITHUB_TOKEN'])
    with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)

def get_release(repo, tag='latest'):
    suffix='/latest' if tag=='latest' else '/tags/'+tag
    data=json_url(f'https://api.github.com/repos/{repo}/releases{suffix}')
    if data.get('draft') or data.get('prerelease'):
        raise RuntimeError('RUNTIME_TOOL_NOT_STABLE: '+repo)
    return data

def acquire(repo, tag, asset_rule, tool_names, target, max_size=350*1024*1024):
    release=get_release(repo,tag)
    candidates=[a for a in release.get('assets',[]) if re.fullmatch(asset_rule,a['name'],re.I)]
    if len(candidates)!=1:
        raise RuntimeError(f'TOOL_ASSET_CHANGED {repo} /{asset_rule}/: found {len(candidates)}')
    asset=candidates[0]
    if asset.get('size',0)<=0 or asset['size']>max_size:
        raise RuntimeError('TOOL_SIZE_UNEXPECTED '+asset['name'])
    url=asset['browser_download_url']
    if not url.startswith('https://github.com/'+repo+'/releases/download/'):
        raise RuntimeError('UNTRUSTED_TOOL_DOWNLOAD '+url)
    destination=target/(asset['name']+'.download')
    req=urllib.request.Request(url,headers={'User-Agent':'OnTheSpot-PortableApps-Builder'})
    size=0;hashobj=hashlib.sha256()
    with urllib.request.urlopen(req,timeout=180) as r, destination.open('wb') as out:
        while True:
            chunk=r.read(1<<20)
            if not chunk:break
            size+=len(chunk)
            if size>max_size:raise RuntimeError('TOOL_DOWNLOAD_TOO_LARGE')
            hashobj.update(chunk);out.write(chunk)
    if size!=asset['size']:
        raise RuntimeError('TOOL_DOWNLOAD_SIZE_MISMATCH')
    sha=hashobj.hexdigest()
    if asset.get('digest') and asset['digest']!='sha256:'+sha:
        raise RuntimeError('TOOL_ASSET_SHA256_MISMATCH')
    found={}
    with zipfile.ZipFile(destination) as z:
        for item in z.infolist():
            if item.is_dir():continue
            name=Path(item.filename.replace('\\','/')).name.lower()
            if name in tool_names:
                if name in found:raise RuntimeError('TOOL_DUPLICATE_EXE: '+name)
                if item.file_size>180*1024*1024:raise RuntimeError('TOOL_EXE_SIZE_UNEXPECTED')
                with z.open(item) as src,(target/name).open('wb') as dst:shutil.copyfileobj(src,dst)
                found[name]=hashlib.sha256((target/name).read_bytes()).hexdigest()
    destination.unlink()
    if set(found)!=set(tool_names):raise RuntimeError('TOOL_EXE_MISSING: '+repr(set(tool_names)-set(found)))
    return {'repo':repo, 'release':release['tag_name'], 'url':url,
            'asset':asset['name'], 'asset_sha256':sha,'executable_sha256':found}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--stage',required=True)
    a=p.parse_args();stage=Path(a.stage);target=stage/'App'/'OnTheSpot'/'tools'
    target.mkdir(parents=True,exist_ok=True)
    docker=(Path(a.source)/'Dockerfile').read_text(encoding='utf-8')
    match=re.search(r'denoland/deno:bin-([\d.]+)',docker)
    if not match:raise RuntimeError('UPSTREAM_DENO_TOOLCHAIN_CHANGED: review Dockerfile')
    # Match explicitly named Windows release assets, never wildcard arbitrary binaries.
    records={
      'ffmpeg':acquire('FFmpeg-Builds/FFmpeg-Builds','latest',r'ffmpeg-master-latest-win64-gpl\.zip',
                      ['ffmpeg.exe','ffprobe.exe'],target),
      'deno':acquire('denoland/deno','v'+match.group(1),r'deno-x86_64-pc-windows-msvc\.zip',
                     ['deno.exe'],target)
    }
    (stage/'Other'/'Source').mkdir(parents=True,exist_ok=True)
    (stage/'Other'/'Source'/'RUNTIME-TOOLS.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(records,indent=2))

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'TRUSTED_RUNTIME_TOOL_FAILED: {e}',file=sys.stderr);sys.exit(1)
