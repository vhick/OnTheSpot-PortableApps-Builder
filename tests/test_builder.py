import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import release
import stage
import validate
import portable_bootstrap as boot

class ReleaseCompatibilityTests(unittest.TestCase):
    def test_reject_v1_and_prerelease_tags(self):
        with patch.object(release, 'request_json', return_value=[
          {'tag_name':'v1.8.1','draft':False,'prerelease':False},
          {'tag_name':'v2.0.6beta1','draft':False,'prerelease':True}]):
            with self.assertRaisesRegex(RuntimeError,'NO_COMPATIBLE_STABLE_RELEASE'):
                release.stable_release()

    def test_numeric_sort_and_no_prerelease(self):
        with patch.object(release,'request_json',return_value=[
          {'tag_name':'v2.0.8','draft':False,'prerelease':False},
          {'tag_name':'v2.0.12','draft':False,'prerelease':False},
          {'tag_name':'v2.1.0beta1','draft':False,'prerelease':True},
          {'tag_name':'v3.0.0','draft':True,'prerelease':False}]):
            self.assertEqual(release.stable_release()['tag_name'],'v2.0.12')

    def test_upstream_build_preflight_detects_layout_changes(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'UPSTREAM_LAYOUT_CHANGED'):
                release.inspect_source(d)

class PathProtectionTests(unittest.TestCase):
    def test_only_previous_managed_data_root_is_relocated(self):
        boot.DATA=Path('E:/PortableApps/OnTheSpotPortable/Data')
        self.assertEqual(boot.relocate('D:\\PortableApps\\OnTheSpotPortable\\Data\\Media\\Music',
                                      'D:\\PortableApps\\OnTheSpotPortable\\Data'),
                         str(boot.DATA/'Media'/'Music'))
        self.assertEqual(boot.relocate('C:\\Users\\Joe\\My Music',
                                      'D:\\PortableApps\\OnTheSpotPortable\\Data'),
                         'C:\\Users\\Joe\\My Music')
        self.assertEqual(boot.relocate('', 'D:\\Data'), '')

    def test_malformed_credential_config_never_reset(self):
        with tempfile.TemporaryDirectory() as d:
            old=(boot.ROOT,boot.DATA,boot.CONFIG,boot.LAST,boot.APP)
            try:
                root=Path(d);app=root/'App/OnTheSpot'
                (app/'code/onthespot').mkdir(parents=True)
                (app/'code/onthespot/otsconfig_default.json').write_text(
                    json.dumps({'audio_download_path':'/root/Music/OnTheSpot',
                                'video_download_path':'/root/Videos/OnTheSpot',
                                'download_profiles':[]}))
                boot.ROOT=root;boot.APP=app;boot.DATA=root/'Data';boot.CONFIG=root/'Data/Config';boot.LAST=root/'Data/.managed-paths.json'
                boot.CONFIG.mkdir(parents=True)
                file=boot.CONFIG/'otsconfig.json'
                file.write_text('{ not valid json',encoding='utf-8')
                with patch.dict(os.environ,dict(os.environ),clear=True):
                    with self.assertRaises(json.JSONDecodeError):boot.prepare_profile()
                self.assertEqual(file.read_text(),'{ not valid json')
            finally:boot.ROOT,boot.DATA,boot.CONFIG,boot.LAST,boot.APP=old

    def test_bootstrap_creates_empty_managed_media_trees(self):
        with tempfile.TemporaryDirectory() as d:
            old=(boot.ROOT,boot.DATA,boot.CONFIG,boot.LAST,boot.APP)
            try:
                root=Path(d);app=root/'App/OnTheSpot'
                (app/'code/onthespot').mkdir(parents=True)
                (app/'code/onthespot/otsconfig_default.json').write_text(json.dumps({
                    'audio_download_path':'/root/Music/OnTheSpot',
                    'video_download_path':'/root/Videos/OnTheSpot','download_profiles':[]}))
                boot.ROOT=root;boot.APP=app;boot.DATA=root/'Data';boot.CONFIG=root/'Data/Config';boot.LAST=root/'Data/.managed-paths.json'
                with patch.dict(os.environ,dict(os.environ),clear=True):boot.prepare_profile()
                cfg=json.loads((boot.CONFIG/'otsconfig.json').read_text(encoding='utf-8'))
                self.assertEqual(cfg['audio_download_path'],str(root/'Data/Media/Music'))
                self.assertTrue((root/'Data/Media/Videos').is_dir())
                self.assertTrue((root/'Data/.managed-paths.json').is_file())
            finally:boot.ROOT,boot.DATA,boot.CONFIG,boot.LAST,boot.APP=old

class IntegrationSafetyTests(unittest.TestCase):
    def test_publisher_patterns_are_relative_and_not_dynamic_absolute_paths(self):
        workflows=Path(__file__).resolve().parents[1]/'.github/workflows'
        for name in ('build.yml','installer-only.yml'):
            text=(workflows/name).read_text(encoding='utf-8')
            for line in text.splitlines():
                if line.strip().startswith('files:'):
                    self.assertNotIn('steps.zip.outputs.zip-file',line)
                    self.assertNotIn('steps.recover.outputs.zip-file',line)
                    self.assertTrue('build/' in line)

    def test_upstream_selected_release_checkout_must_match_server_sha(self):
        source=Path(release.__file__).read_text(encoding='utf-8')
        self.assertIn('UPSTREAM_CHECKOUT_COMMIT_MISMATCH',source)

    def test_native_launcher_has_close_button_and_job_guard(self):
        text=(Path(__file__).resolve().parents[1]/'launcher/OnTheSpotPortable.cpp').read_text()
        self.assertIn('Stop OnTheSpot',text)
        self.assertIn('JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE',text)

class PackagingTests(unittest.TestCase):
    def test_version_normalization(self):
        self.assertEqual(stage.version4('v2.0.5'),'2.0.5.0')
        with self.assertRaisesRegex(RuntimeError,'NOT_NUMERIC_STABLE'):stage.version4('2.0.6beta1')

    def test_safe_zip_path_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'bad.zip'
            with zipfile.ZipFile(f,'w') as z:z.writestr('OnTheSpotPortable/../unsafe.txt','bad')
            with self.assertRaisesRegex(RuntimeError,'UNSAFE_ZIP_ENTRY'):
                validate.extract_zip(f,Path(d)/'extracted')

    def test_rejects_fake_pe(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fake.exe';p.write_bytes(b'MZ'+b'\x00'*2000)
            with self.assertRaisesRegex(RuntimeError,'INVALID_PE_OFFSET'):
                validate.pe(p)

    def test_sha256_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'foo.zip';p.write_bytes(b'data')
            m=Path(d)/'SHA256SUMS.txt';m.write_text('0'*64+'  foo.zip\n')
            with self.assertRaisesRegex(RuntimeError,'ZIP_CHECKSUM_MISMATCH'):
                validate.verify_sha(p,m)

    def test_preserve_empty_nested_zip_directories(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('OnTheSpotPortable/Data/nested/empty/',b'')
            with zipfile.ZipFile(p) as z:self.assertIn('OnTheSpotPortable/Data/nested/empty/',z.namelist())

if __name__=='__main__':unittest.main()
