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

class IconResolutionTests(unittest.TestCase):
    @staticmethod
    def add_image(root,rel,wh=(128,128),format=None):
        from PIL import Image
        p=Path(root)/rel;p.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGBA',wh,(45,122,176,255)).save(p,format=format)
        return p

    def test_preferred_repo_brand_survives_multiple_logo_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.add_image(tmp,'assets/logos/repository_logo.png')
            self.add_image(tmp,'assets/logos/old_logo.png')
            self.add_image(tmp,'ui/public/logo.png')
            chosen,metadata=stage.choose_upstream_icon(tmp)
            self.assertEqual(chosen,p)
            self.assertEqual(metadata['path'],'assets/logos/repository_logo.png')

    def test_missing_link_falls_back_to_versioned_app_branding(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'README.md').write_text('<img src="assets/logos/repository_logo.png" alt="Repository Logo">')
            p=self.add_image(tmp,'ui/public/onthespot.png')
            self.add_image(tmp,'assets/logos/bandcamp_logo.png')
            self.add_image(tmp,'assets/images/settings.png')
            chosen,_=stage.choose_upstream_icon(tmp)
            self.assertEqual(chosen,p)

    def test_valid_repo_readme_link_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'README.md').write_text('<img alt="Repository Logo" src="assets/brand/official_v2.png">')
            p=self.add_image(tmp,'assets/brand/official_v2.png')
            self.add_image(tmp,'assets/logos/logo.png')
            chosen,_=stage.choose_upstream_icon(tmp)
            self.assertEqual(chosen,p)

    def test_readme_traversal_and_remote_image_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'README.md').write_text('<img alt="Repository Logo" src="../../secrets/icon.png"><img alt="Repository Logo" src="https://example.test/logo.png">')
            self.assertEqual(stage._readme_images(Path(tmp)),[])

    def test_corrupt_and_service_icons_never_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp,'assets/logos/repository_logo.png');bad.parent.mkdir(parents=True)
            bad.write_bytes(b'broken')
            self.add_image(tmp,'assets/logos/spotify_logo.png')
            p=self.add_image(tmp,'ui/public/onthespot_icon.png')
            chosen,_=stage.choose_upstream_icon(tmp)
            self.assertEqual(chosen,p)

    def test_only_service_art_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.add_image(tmp,'assets/logos/spotify_logo.png')
            self.add_image(tmp,'assets/logos/qobuz_logo.png')
            with self.assertRaisesRegex(RuntimeError,'UPSTREAM_APP_ICON_NOT_FOUND'):
                stage.choose_upstream_icon(tmp)

    def test_unofficial_fallback_is_explicit_and_never_uses_service_logo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.add_image(tmp,'assets/logos/spotify_logo.png')
            chosen,metadata=stage.choose_upstream_icon(tmp,allow_fallback=True)
            self.assertIsNone(chosen)
            self.assertEqual(metadata['selection_method'],'independent-unofficial-fallback-v1')
            self.assertFalse(metadata['path'])

    def test_non_image_logo_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp,'assets/logos/logo.png');p.parent.mkdir(parents=True)
            p.write_text('not an image')
            with self.assertRaisesRegex(RuntimeError,'UPSTREAM_APP_ICON_NOT_FOUND'):
                stage.choose_upstream_icon(tmp)

class ProductionReleaseProbeTests(unittest.TestCase):
    """Tests for first-time publishing and fail-closed API errors."""

    def setUp(self):
        import probe_release
        self.probe_release=probe_release
        self.repo='vhick/OnTheSpot-PortableApps-Builder'
        self.tag='portable-v2.0.5-b1r3-official'
        self.token='fake-test-only-token'

    def test_absent_release_is_not_an_error(self):
        from urllib.error import HTTPError
        from io import BytesIO
        def fake_get(url, token):
            if '/releases/tags/' in url:
                raise HTTPError(url,404,'Not Found',{},BytesIO(b''))
            return {'full_name':self.repo}
        with patch.object(self.probe_release,'api_get_json',side_effect=fake_get):
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'GITHUB_OUTPUT'
                self.assertFalse(self.probe_release.probe('skip',self.repo,self.tag,self.token,output))
                self.assertEqual(output.read_text(encoding='utf-8'),'skip=false\n')

    def test_existing_release_skips_production_build(self):
        with patch.object(self.probe_release,'api_get_json',return_value={'tag_name':self.tag}):
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'GITHUB_OUTPUT'
                self.assertTrue(self.probe_release.probe('skip',self.repo,self.tag,self.token,output))
                self.assertEqual(output.read_text(encoding='utf-8'),'skip=true\n')

    def test_existing_release_blocks_installer_only_publish(self):
        with patch.object(self.probe_release,'api_get_json',return_value={'tag_name':self.tag}):
            with self.assertRaisesRegex(RuntimeError,'PRODUCTION_RELEASE_ALREADY_EXISTS'):
                self.probe_release.probe('guard',self.repo,self.tag,self.token)

    def test_first_time_installer_only_publish_is_allowed(self):
        from urllib.error import HTTPError
        from io import BytesIO
        def fake_get(url,token):
            if '/releases/tags/' in url:
                raise HTTPError(url,404,'Not Found',{},BytesIO(b''))
            return {'full_name':self.repo}
        with patch.object(self.probe_release,'api_get_json',side_effect=fake_get):
            self.assertFalse(self.probe_release.probe('guard',self.repo,self.tag,self.token))

    def test_api_permission_denial_is_fatal_not_missing(self):
        from urllib.error import HTTPError
        from io import BytesIO
        url='https://api.github.com/repos/'+self.repo+'/releases/tags/'+self.tag
        with patch.object(self.probe_release,'api_get_json',side_effect=HTTPError(url,403,'Forbidden',{},BytesIO(b''))):
            with self.assertRaisesRegex(RuntimeError,'RELEASE_PROBE_API_FAILED: HTTP 403'):
                self.probe_release.release_exists(self.repo,self.tag,self.token)

    def test_repository_inaccessible_404_is_fatal(self):
        from urllib.error import HTTPError
        from io import BytesIO
        def fake_get(url,token):
            raise HTTPError(url,404,'Not Found',{},BytesIO(b''))
        with patch.object(self.probe_release,'api_get_json',side_effect=fake_get):
            with self.assertRaisesRegex(RuntimeError,'RELEASE_REPOSITORY_ACCESS_FAILED: HTTP 404'):
                self.probe_release.release_exists(self.repo,self.tag,self.token)

    def test_malformed_api_body_and_tag_are_rejected(self):
        with patch.object(self.probe_release,'api_get_json',return_value={'tag_name':'different'}):
            with self.assertRaisesRegex(RuntimeError,'RELEASE_PROBE_RESPONSE_INVALID'):
                self.probe_release.release_exists(self.repo,self.tag,self.token)
        with self.assertRaisesRegex(RuntimeError,'RELEASE_TAG_INVALID'):
            self.probe_release.release_exists(self.repo,'not-a-release-tag',self.token)
        with self.assertRaisesRegex(RuntimeError,'RELEASE_PROBE_AUTH_MISSING'):
            self.probe_release.release_exists(self.repo,self.tag,'')

    def test_no_bare_gh_release_view_or_hardcoded_repack_revision(self):
        base=Path(__file__).resolve().parents[1]/'.github/workflows'
        build=(base/'build.yml').read_text(encoding='utf-8')
        repack=(base/'installer-only.yml').read_text(encoding='utf-8')
        self.assertNotIn('gh release view',build)
        self.assertNotIn('gh release view',repack)
        self.assertIn('probe_release.py',build)
        self.assertIn('probe_release.py',repack)
        self.assertIn('package-revision: ${{ steps.recover.outputs.original-revision }}',repack)

if __name__ == "__main__":
    unittest.main()
