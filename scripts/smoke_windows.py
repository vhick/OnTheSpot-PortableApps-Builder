"""Real Windows local API/UI smoke. Must run on an extracted test copy, not release stage."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from validate import extract_zip


def smoke(root):
    root=Path(root)
    app=root/'OnTheSpotPortable.exe'
    # Avoid collisions with preexisting 6767 service. Test argument forwarding.
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    proc=subprocess.Popen([str(app),'--port',str(port),'--no-browser'],cwd=root,
                          creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        ready=False
        end=time.monotonic()+150
        while time.monotonic()<end:
            if proc.poll() is not None:
                raise RuntimeError(f'WINDOWS_RUNTIME_EXITED_EARLY: code={proc.returncode}')
            try:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(f'http://127.0.0.1:{port}/', timeout=2) as resp:
                    text=resp.read(100000).decode('utf-8','replace').lower()
                    if resp.status==200 and ('<html' in text or '<!doctype' in text):
                        ready=True;break
            except Exception:time.sleep(1)
        if not ready:raise RuntimeError('LOCAL_BROWSER_UI_DID_NOT_START_WITHIN_150S')
        config=root/'Data/Config/otsconfig.json'
        if not config.is_file():raise RuntimeError('PORTABLE_CONFIG_NOT_CREATED')
        d=json.loads(config.read_text(encoding='utf-8'))
        for key in ('audio_download_path','video_download_path'):
            p=Path(d[key]).resolve()
            if not p.is_relative_to((root/'Data').resolve()):
                raise RuntimeError('DEFAULT_DOWNLOAD_NOT_PORTABLE: '+key+'='+str(p))
        print('WINDOWS_RUNTIME_SMOKE_PASS: local HTTP UI 200, Data config, portable download folders')
    finally:
        # Job-object with KILL_ON_JOB_CLOSE ensures the Python child terminates.
        if proc.poll() is None:
            proc.kill()
        try:proc.wait(timeout=30)
        except subprocess.TimeoutExpired:raise RuntimeError('PORTABLE_PROCESS_SHUTDOWN_TIMEOUT')
        time.sleep(1)
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError('CHILD_SERVER_LEAK_AFTER_LAUNCHER_SHUTDOWN')

def main():
    p=argparse.ArgumentParser();p.add_argument('--zip',required=True)
    args=p.parse_args()
    if os.name!='nt':raise RuntimeError('WINDOWS_SMOKE_REQUIRES_REAL_WINDOWS')
    with tempfile.TemporaryDirectory(prefix='OnTheSpot-Portable-Smoke-') as d:
        root=extract_zip(args.zip,d)
        smoke(root)
if __name__=='__main__':
    try:main()
    except Exception as e:print('WINDOWS_RUNTIME_SMOKE_FAILED:',e,file=sys.stderr);sys.exit(1)
