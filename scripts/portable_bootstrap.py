"""OnTheSpot v2 portable bootstrap: owns only portable Data, never host profiles.

This runs in the app's actual bundled Python and before importing OnTheSpot.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
APP = Path(__file__).resolve().parent
DATA = ROOT / 'Data'
CONFIG = DATA / 'Config'
LAST = DATA / '.managed-paths.json'


def under(path, previous):
    if not path or not previous:
        return None
    # Windows drive letters need a case-insensitive comparison even when the
    # previous drive has changed (also allows OS-independent regression tests).
    import ntpath
    if ntpath.isabs(path) and ntpath.isabs(previous):
        old=ntpath.normcase(ntpath.normpath(previous)).rstrip('\\/')
        value=ntpath.normcase(ntpath.normpath(path))
        if value == old or value.startswith(old + '\\'):
            return Path(*ntpath.normpath(path)[len(ntpath.normpath(previous)):].lstrip('\\/').split('\\'))
        return None
    try:
        p=Path(path);base=Path(previous)
        return p.relative_to(base) if p.is_absolute() else None
    except (ValueError,OSError):
        return None


def relocate(value, previous_data):
    if not isinstance(value, str) or not value:
        return value
    rel = under(value, previous_data)
    return str(DATA / rel) if rel is not None else value


def prepare_profile():
    for path in [DATA, CONFIG, DATA/'Cache',DATA/'Home',DATA/'Temp',DATA/'Logs',
                 DATA/'Media'/'Music', DATA/'Media'/'Videos',DATA/'Environment'/'Roaming',
                 DATA/'Environment'/'Local']:
        path.mkdir(parents=True, exist_ok=True)
    # Native upstream variables. Deliberately set before any application import.
    for k,v in {'ONTHESPOTDIR':CONFIG,'ONTHESPOTCACHEDIR':DATA/'Cache',
                'ONTHESPOT_WEBUI_DIST': APP/'ui','APPDATA':DATA/'Environment'/'Roaming',
                'LOCALAPPDATA': DATA/'Environment'/'Local','HOME':DATA/'Home',
                'USERPROFILE':DATA/'Home','TEMP': DATA/'Temp','TMP':DATA/'Temp',
                'XDG_CACHE_HOME':DATA/'Cache', 'XDG_CONFIG_HOME':CONFIG,
                'YTDLP_CACHE_DIR':DATA/'Cache'/'yt-dlp', 'PYTHONUSERBASE':DATA/'Environment'/'Python',
                'PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION':'python', 'PYTHONDONTWRITEBYTECODE':'1',
                'FFMPEG_PATH': APP/'tools'/'ffmpeg.exe', 'ONTHESPOT_HOST':'127.0.0.1'} .items():
        os.environ[k]=str(v)
    os.environ['PATH'] = str(APP/'tools') + os.pathsep + os.environ.get('PATH','')
    # This is intentionally a pre-existing persistent config, not App/DefaultData
    # copied over Data during reinstall. Preserve all unrelated and custom keys.
    config_file=CONFIG/'otsconfig.json'
    upstream_default = APP/'code'/'onthespot'/'otsconfig_default.json'
    if not upstream_default.is_file():
        raise RuntimeError('PORTABLE_DEFAULT_CONFIG_MISSING')
    fresh = not config_file.exists()
    if fresh:
        settings=json.loads(upstream_default.read_text(encoding='utf-8'))
    else:
        # Fail closed on a damaged config rather than erasing accounts/settings.
        settings=json.loads(config_file.read_text(encoding='utf-8'))
        if not isinstance(settings,dict):
            raise RuntimeError('PORTABLE_CONFIG_INVALID: expected JSON object')
    old={}
    if LAST.is_file():
        old=json.loads(LAST.read_text(encoding='utf-8'))
        if not isinstance(old,dict):
            raise RuntimeError('PORTABLE_PATH_MANIFEST_INVALID: preserve Data and investigate')
    prev=old.get('data_root','')
    def fixpath(key, target, docker_default):
        cur=settings.get(key)
        if fresh or not cur or cur == docker_default:
            settings[key]=str(target)
        elif prev:
            settings[key]=relocate(cur,prev)
    fixpath('audio_download_path', DATA/'Media'/'Music', '/root/Music/OnTheSpot')
    fixpath('video_download_path', DATA/'Media'/'Videos', '/root/Videos/OnTheSpot')
    if prev:
        for key in ('export_folder_path','playlist_backup_folder_path'):
            if key in settings:settings[key]=relocate(settings[key],prev)
        profiles=settings.get('download_profiles')
        if isinstance(profiles,list):
            for profile in profiles:
                if isinstance(profile,dict) and 'download_path' in profile:
                    profile['download_path']=relocate(profile['download_path'],prev)
    # User-selected paths outside Data are left untouched, not harvested.
    if fresh or (prev and str(DATA)!=prev) or settings.get('audio_download_path') == '/root/Music/OnTheSpot':
        atomic_json(config_file,settings)
    elif not config_file.exists():
        atomic_json(config_file,settings)
    else:
        # Always save only when relocation has actually changed values.
        original=json.loads(config_file.read_text(encoding='utf-8'))
        if settings!=original:atomic_json(config_file,settings)
    atomic_json(LAST,{'data_root':str(DATA)})
    # Prevent code directory writes; user content belongs under Data.
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(APP/'runtime'/'Lib'/'site-packages'))
    sys.path.insert(0,str(APP/'code'))


def atomic_json(path, data):
    temp=path.with_suffix(path.suffix+'.pending')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temp,path)


def open_when_ready(port):
    for _ in range(120):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=0.75):
                webbrowser.open(f'http://127.0.0.1:{port}/',new=1)
                return
        except OSError:
            time.sleep(0.5)


def main():
    parser=argparse.ArgumentParser(description='OnTheSpot local portable server')
    parser.add_argument('--port',type=int,default=6767)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:raise RuntimeError('Invalid local server port')
    prepare_profile()
    if not (APP/'runtime'/'python.exe').is_file():
        raise RuntimeError('BUNDLED_PYTHON_MISSING')
    if not (APP/'tools'/'ffmpeg.exe').is_file():
        raise RuntimeError('FFMPEG_MISSING: required tool was not packaged')
    if not (APP/'ui'/'index.html').is_file():
        raise RuntimeError('WEB_UI_MISSING')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',args.port)) == 0:
            raise RuntimeError(f'Port {args.port} is already in use: no second instance started')
    if not args.no_browser:
        threading.Thread(target=open_when_ready,args=(args.port,),daemon=True).start()
    import uvicorn
    server = uvicorn.Server(uvicorn.Config('onthespot.main:app',host='127.0.0.1',
                      port=args.port,log_level='info',reload=False,workers=1,
                      access_log=False))
    event_name=os.environ.get('ONTHESPOT_STOP_EVENT')
    if os.name=='nt' and event_name:
        def graceful_stop():
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenEventW.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_wchar_p]
            kernel.OpenEventW.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
            kernel.WaitForSingleObject.restype=ctypes.c_uint32
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=kernel.OpenEventW(0x00100000,False,event_name)
            if not handle:
                return
            try:
                if kernel.WaitForSingleObject(handle,0xffffffff)==0:
                    server.should_exit=True
            finally:kernel.CloseHandle(handle)
        threading.Thread(target=graceful_stop,name='PortableServerStop',daemon=True).start()
    server.run()

if __name__=='__main__':
    try:main()
    except Exception as ex:
        DATA.mkdir(parents=True,exist_ok=True)
        (DATA/'portable-startup-error.txt').write_text(str(ex)+'\n',encoding='utf-8')
        print('OnTheSpot Portable startup error:',ex,file=sys.stderr)
        raise
