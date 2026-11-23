"""Read-only compatibility watch. Does not edit dependencies or publish releases."""
import json
import sys
from pathlib import Path
from release import request_json,stable_release


def main():
    r=stable_release()
    pack=request_json('https://api.github.com/repos/vhick/Portable-Package-Builder/releases/tags/v1.1.0')
    publisher=request_json('https://api.github.com/repos/vhick/portable-release-publisher/releases/tags/v1.1.1')
    result={
      'newest_upstream_stable':r['tag_name'],
      'known_app_successful_versions':[],
      'shared_package_builder_release':pack.get('tag_name'),
      'shared_package_builder_pinned_commit':'9bf686ec29a46073ca3c27638e62862eb8cc9079',
      'shared_publisher_release':publisher.get('tag_name'),
      'shared_publisher_pinned_commit':'cb64f86ac2d8c67506db5832de07f9ff58cbeaeb',
      'action':'Manual review only. No upstream or shared action version is automatically adopted.'
    }
    Path('maintenance-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as e:print('MAINTENANCE_QUERY_FAILED:',e,file=sys.stderr);sys.exit(1)
