"""PortableApps staging, icon generation, independent ZIP, and stage checks."""
import argparse
import hashlib
import html
import os
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

# Image selection uses the upstream repository content; never download a
# substitute logo from an unverified site or select service provider artwork.
# The README image is only a hint: upstream may leave links pointing to
# removed or relocated assets, so it cannot be treated as a mandatory path.
IMAGE_SUFFIXES={'.png','.webp','.ico','.jpg','.jpeg'}
BLOCKED_NAMES={'spotify','youtube','apple','deezer','tidal','bandcamp',
               'qobuz','amazon','soundcloud','napster','generic','netflix',
               'search','download','queue','settings','play','pause','stop',
               'menu','link','discord','badge','screenshot','banner'}
PREFERRED_IMAGES=(
    'assets/logos/repository_logo.png',
    'assets/logos/onthespot.png',
    'assets/logos/onthespot_logo.png',
    'assets/logos/logo.png',
    'assets/logo.png',
    'assets/icon.png',
    'ui/public/onthespot.png',
    'ui/public/logo.png',
    'ui/public/icon.png',
    'ui/public/favicon.png',
    'src/onthespot/resources/icon.png',
    'src/onthespot/resources/icon.ico',
    'api/src/onthespot/resources/icon.png',
)

def _safe_relative_image(source, raw):
    """Reject external URLs, traversal, encoded paths and non-image aliases."""
    from pathlib import PurePosixPath
    from urllib.parse import unquote, urlsplit
    if not isinstance(raw,str) or not raw.strip() or '\\' in raw:
        return None
    raw=html.unescape(raw.strip())
    parsed=urlsplit(raw)
    if parsed.scheme or parsed.netloc or raw.startswith(('/', '\\')):
        return None
    # No URL-decoding remote or suspicious paths.
    if '%' in raw or '#' in raw or '?' in raw or ':' in raw:
        return None
    path=PurePosixPath(raw.replace('\\','/'))
    if path.is_absolute() or '..' in path.parts or path.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    candidate=source.joinpath(*path.parts)
    try:
        if not candidate.resolve().is_relative_to(source.resolve()):return None
    except OSError:return None
    return candidate if candidate.is_file() else None

def _readme_images(source):
    """Read only source-local logo links labeled as upstream project branding."""
    from html.parser import HTMLParser
    class Collector(HTMLParser):
        def __init__(self):super().__init__();self.images=[]
        def handle_starttag(self,tag,attrs):
            if tag.lower()!='img':return
            d={a.lower():v for a,v in attrs if a and v}
            if any(x in d.get('alt','').lower() for x in ('repository logo','onthespot logo','app logo')):
                self.images.append(d.get('src',''))
    path=source/'README.md'
    if not path.is_file():return []
    doc=path.read_text(encoding='utf-8-sig',errors='replace')[:512000]
    c=Collector();c.feed(doc)
    # Also support Markdown ![Repository Logo](...)
    for link in re.findall(r'!\[(?:Repository Logo|OnTheSpot Logo|App Logo)\]\(([^)]*)\)',doc,re.I):
        c.images.append(link.strip().split(' ')[0])
    return [p for x in c.images if (p:=_safe_relative_image(source,x)) is not None]

def _score_image(source,path,readme_links):
    rel=path.relative_to(source).as_posix()
    words=set(filter(None,re.split(r'[^a-z0-9]+',rel.lower())))
    stem=path.stem.lower()
    # Exclude support/service icons, screenshots and artwork not for app identity.
    if words & BLOCKED_NAMES:return -1
    if 'images' in words and 'logo' not in words and 'icon' not in words:return -1
    score=0
    if path in readme_links:score+=400
    if rel in PREFERRED_IMAGES:score+=190-len(PREFERRED_IMAGES) + (len(PREFERRED_IMAGES)-PREFERRED_IMAGES.index(rel))
    if stem=='repository_logo':score+=100
    if 'onthespot' in stem or 'on_the_spot' in stem:score+=90
    if stem in {'appicon','app_icon','ots_icon','ots_logo'}:score+=85
    if 'logo' in stem:score+=60
    if 'icon' in stem or 'favicon' in stem:score+=45
    if 'logo' in words:score+=20
    if 'logos' in words or 'branding' in words:score+=25
    if 'icons' in words:score+=15
    if 'assets' in words:score+=8
    if len(words & {'docs','tests','test','screenshots','screens','samples'}):score-=65
    return score

def choose_upstream_icon(source, *, allow_fallback=False):
    """Return verified application artwork and a reproducible origin record.

    Rank branding, verify Pillow can decode and that geometry is suitable for
    application icons. Do not choose an unrelated integration logo just because
    it is the only PNG named 'logo'.
    """
    from PIL import Image
    source=Path(source).resolve()
    readme_links=_readme_images(source)
    candidates=[]
    for path in source.rglob('*'):
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in IMAGE_SUFFIXES:continue
        score=_score_image(source,path,readme_links)
        if score<45:continue
        try:
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                w,h=im.size
                if w<32 or h<32 or max(w,h)>8192:continue
                ratio=max(w,h)/min(w,h)
                if ratio>3:continue
                score+=35 if ratio<=1.35 else (15 if ratio<=2 else 0)
                score+=min(15,min(w,h)//64)
        except (OSError,ValueError,Image.DecompressionBombError):continue
        candidates.append((score,path.relative_to(source).as_posix(),path))
    if not candidates:
        if allow_fallback:
            print('UNOFFICIAL_ICON_FALLBACK: no suitable upstream branding; using embedded independent launcher icon (not upstream logo)')
            return None, {'path':'', 'sha256':'', 'selection_method':'independent-unofficial-fallback-v1',
                          'note':'No verified upstream app-brand image; original independent launcher art, not official upstream branding'}
        raise RuntimeError('UPSTREAM_APP_ICON_NOT_FOUND: no trustworthy readable app icon; inspected README logo hints, assets and UI branding (other service logos rejected)')
    candidates.sort(key=lambda x:(-x[0],x[1]))
    score,rel,path=candidates[0]
    import hashlib
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    print('UPSTREAM_ICON_SELECTED:',rel,'score:',score,'sha256:',sha)
    return path, {'path':rel,'sha256':sha,'selection_score':score,'selection_method':'source-branding-scored-v1'}

def init(stage,source,identity):
    root=Path(stage)/APPNAME
    info=json.loads(Path(identity).read_text(encoding='utf-8'))
    v=info['upstream_version'];version=version4(v)
    dirs=['App/AppInfo/Launcher','App/OnTheSpot','App/DefaultData','Data','Other/Source']
    for d in dirs:(root/d).mkdir(parents=True,exist_ok=True)
    # No Data defaults are copied over during installation or upgrade.
    source=Path(source)
    icon_file,icon_origin=choose_upstream_icon(source,allow_fallback=True)
    info['upstream_icon']=icon_origin
    try:
        from PIL import Image
    except ImportError as e:raise RuntimeError('PILLOW_BUILD_DEPENDENCY_MISSING') from e
    icon_info=root/'App/AppInfo'
    if icon_file is not None:
        img=Image.open(icon_file).convert('RGBA')
    else:
        # Original neutral app-type artwork for an independently branded
        # launcher. This is NOT represented as the official upstream icon.
        from PIL import ImageDraw
        img=Image.new('RGBA',(256,256),(0,0,0,0))
        draw=ImageDraw.Draw(img)
        draw.rounded_rectangle((6,6,250,250),radius=52,fill=(13,45,62,255))
        draw.ellipse((45,45,210,210),outline=(50,200,150,255),width=11)
        draw.line((97,71,97,173),fill=(255,255,255,255),width=12)
        draw.line((97,72,155,88),fill=(255,255,255,255),width=12)
        draw.line((155,88,155,162),fill=(255,255,255,255),width=12)
        draw.ellipse((62,159,106,195),fill=(255,255,255,255))
        draw.ellipse((120,149,166,185),fill=(255,255,255,255))
    from PIL import ImageOps
    for size in (16,32):
        ImageOps.pad(img,(size,size),method=Image.Resampling.LANCZOS,color=(0,0,0,0)).save(icon_info/f'appicon_{size}.png')
    ImageOps.pad(img,(256,256),method=Image.Resampling.LANCZOS,color=(0,0,0,0)).save(icon_info/'appicon.ico',format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(256,256)])
    if (icon_info/'appicon.ico').stat().st_size<100:raise RuntimeError('ICON_COMPILE_FAILED')
    ini='''[Format]\nType=PortableApps.comFormat\nVersion=3.9\n\n[Details]\nName=OnTheSpot Portable\nAppID=OnTheSpotPortable\nPublisher=OnTheSpot contributors & independent builder\nHomepage=https://github.com/ots-downloader/onthespot\nCategory=Music & Video\nDescription=OnTheSpot 2.x local web-app music and media downloader; unofficial portable package.\nLanguage=Multilingual\nTrademarks=OnTheSpot is a project of its upstream contributors.\n\n[License]\nShareable=true\nOpenSource=true\nFreeware=true\nCommercialUse=true\nEULAVersion=1\n\n[Version]\nPackageVersion=VERSION4\nDisplayVersion=DISPLAY b1r4\n\n[Control]\nIcons=1\nStart=OnTheSpotPortable.exe\n'''.replace('VERSION4',version).replace('DISPLAY',v)
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
    info['package_revision']='b1r4'
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
    file=output/f'OnTheSpotPortable_v{safe}_b1r4.zip'
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
