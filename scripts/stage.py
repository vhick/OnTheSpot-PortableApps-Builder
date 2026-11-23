"""PortableApps staging, icon generation, independent ZIP, and stage checks."""
import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

APPNAME='OnTheSpotPortable'

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def version4(s):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)',s)
    if not match:raise RuntimeError('UPSTREAM_VERSION_NOT_NUMERIC_STABLE: '+s)
    return '.'.join(match.groups())+'.0'

def init(stage,source,identity):
    root=Path(stage)/APPNAME
    info=json.loads(Path(identity).read_text(encoding='utf-8'))
    v=info['upstream_version'];version=version4(v)
    dirs=['App/AppInfo/Launcher','App/OnTheSpot','App/DefaultData','Data','Other/Source']
    for d in dirs:(root/d).mkdir(parents=True,exist_ok=True)
    # No Data defaults are copied over during installation or upgrade.
    source=Path(source)
    icon_file=source/'assets/logos/repository_logo.png'
    if not icon_file.is_file():
        icons=[p for p in (source/'assets').rglob('*.png') if 'logo' in p.name.lower()]
        if len(icons)!=1:raise RuntimeError('UPSTREAM_APP_ICON_CHANGED: cannot select a unique logo')
        icon_file=icons[0]
    try:
        from PIL import Image
    except ImportError as e:raise RuntimeError('PILLOW_BUILD_DEPENDENCY_MISSING') from e
    icon_info=root/'App/AppInfo'
    img=Image.open(icon_file).convert('RGBA')
    from PIL import ImageOps
    for size in (16,32):
        ImageOps.pad(img,(size,size),method=Image.Resampling.LANCZOS,color=(0,0,0,0)).save(icon_info/f'appicon_{size}.png')
    ImageOps.pad(img,(256,256),method=Image.Resampling.LANCZOS,color=(0,0,0,0)).save(icon_info/'appicon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(256,256)])
    if (icon_info/'appicon.ico').stat().st_size<100:raise RuntimeError('ICON_COMPILE_FAILED')
    ini='''[Format]\nType=PortableApps.comFormat\nVersion=3.9\n\n[Details]\nName=OnTheSpot Portable\nAppID=OnTheSpotPortable\nPublisher=OnTheSpot contributors & independent builder\nHomepage=https://github.com/ots-downloader/onthespot\nCategory=Music & Video\nDescription=OnTheSpot 2.x local web-app music and media downloader; unofficial portable package.\nLanguage=Multilingual\nTrademarks=OnTheSpot is a project of its upstream contributors.\n\n[License]\nShareable=true\nOpenSource=true\nFreeware=true\nCommercialUse=true\nEULAVersion=1\n\n[Version]\nPackageVersion=VERSION4\nDisplayVersion=DISPLAY b1r2\n\n[Control]\nIcons=1\nStart=OnTheSpotPortable.exe\n'''.replace('VERSION4',version).replace('DISPLAY',v)
    (icon_info/'appinfo.ini').write_text(ini,encoding='utf-8')
    help=root/'help.html'
    if not help.exists():
        help.write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>OnTheSpot Portable help</title></head><body>
<h1>OnTheSpot Portable — {html.escape(v)}</h1><p>Unofficial PortableApps-style build; not endorsed or certified by PortableApps.com.</p>
<p>Start <b>OnTheSpotPortable.exe</b>. The local OnTheSpot web application opens in your default browser at
<a href="http://127.0.0.1:6767/">http://127.0.0.1:6767/</a>. Keep the launcher open while using it.</p>
<p>Settings and encrypted credential files: <code>Data\\Config</code>; cache: <code>Data\\Cache</code>;
media: <code>Data\\Media</code>. On upgrade, preserve the entire <code>Data</code> folder.</p>
<p>Stop the application by closing the launcher window/process; the child server is terminated with it.
Use only services and downloads you are authorized to access.</p>
<p><a href="https://github.com/ots-downloader/onthespot">Official OnTheSpot project</a> |
<a href="https://github.com/ots-downloader/onthespot/issues">Upstream support</a></p></body></html>\n''',encoding='utf-8')
    if not help.read_text(encoding='utf-8').strip().lower().startswith('<!doctype html>'):
        raise RuntimeError('INVALID_ROOT_HELP_HTML')
    info['package_revision']='b1r2'
    (root/'Other/Source/BUILD-IDENTITY.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(source/'LICENSE',root/'Other/Source/ONTHESPOT-GPL-2.0.txt')
    (root/'Other/Source/PORTABLE-LICENSE-NOTICE.txt').write_text(
       'This is an unofficial independent PortableApps-style distribution. OnTheSpot source is GPL-2.0.\n'
       'Source revision and dependencies appear in BUILD-IDENTITY.json.\n'
       'Original source: https://github.com/ots-downloader/onthespot\n'
       'FFmpeg, Deno, Python and dependencies have their own licenses; see upstream licenses.\n'
       'Redistributors must comply with every component license and provide corresponding source where required.\n',encoding='utf-8')
    # GitHub Actions creates the compiled launcher after this stage.
    print('Prepared staging:',root)

def package(stage,output):
    from validate import validate_stage
    root=Path(stage)/APPNAME
    validate_stage(root)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    info=json.loads((root/'Other/Source/BUILD-IDENTITY.json').read_text(encoding='utf-8'))
    safe=info['upstream_version'].lstrip('v')
    file=output/f'OnTheSpotPortable_v{safe}_b1r2.zip'
    with zipfile.ZipFile(file,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for item in sorted(root.rglob('*')):
            rel=item.relative_to(root.parent).as_posix()
            if item.is_symlink():raise RuntimeError('ZIP_STAGING_SYMLINK_REJECTED: '+rel)
            if item.is_dir():
                z.writestr(rel+'/',b'')
            else:z.write(item,rel)
    with zipfile.ZipFile(file) as z:
        error=z.testzip()
        if error:raise RuntimeError('ZIP_INTEGRITY_FAILED: '+error)
    sha=digest(file)
    (output/'SHA256SUMS.txt').write_bytes(f'{sha}  {file.name}\n'.encode('ascii'))
    print('PACKAGED',file,'SHA256',sha)
    if 'GITHUB_OUTPUT' in __import__('os').environ:
        with open(__import__('os').environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
            f.write('zip-file='+str(file.resolve())+'\n')
            f.write('upstream-version='+info['upstream_version']+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','zip'])
    p.add_argument('--stage',default='build/staging');p.add_argument('--source',default='upstream')
    p.add_argument('--identity',default='build/identity.json');p.add_argument('--output',default='build/output')
    args=p.parse_args()
    if args.command=='init':init(args.stage,args.source,args.identity)
    else:package(args.stage,args.output)
if __name__=='__main__':
    try:main()
    except Exception as e:print('STAGING_FAILED:',str(e),file=sys.stderr);sys.exit(1)
