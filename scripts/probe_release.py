#!/usr/bin/env python3
"""Safely check for engine-specific GitHub releases in the current builder repo.

A 404 release is an expected *absence*, not a failure. Other API/auth errors
are fatal. Do not rely on gh(1) exit code 1 or $LASTEXITCODE in PowerShell.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
TAG_PATTERN = re.compile(r'^portable-v?\d+\.\d+\.\d+-b\d+r\d+-(custom-nsis|official)$')


def api_get_json(url, token):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'OnTheSpot-PortableApps-Builder',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Authorization': 'Bearer ' + token,
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def release_exists(repository, tag, token):
    if not REPO_PATTERN.fullmatch(repository):
        raise RuntimeError('RELEASE_REPOSITORY_INVALID: expected owner/repo')
    if not TAG_PATTERN.fullmatch(tag):
        raise RuntimeError('RELEASE_TAG_INVALID: unexpected engine-specific portable tag: ' + tag)
    if not token:
        raise RuntimeError('RELEASE_PROBE_AUTH_MISSING: GITHUB_TOKEN is required')
    repo = urllib.parse.quote(repository, safe='/')
    url = f'https://api.github.com/repos/{repo}/releases/tags/{urllib.parse.quote(tag, safe="")}'
    try:
        release = api_get_json(url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # A missing/private/inaccessible repository can also return 404.
            # Confirm the repo itself is accessible before treating the release as absent.
            try:
                repo_info = api_get_json(f'https://api.github.com/repos/{repo}', token)
            except urllib.error.HTTPError as repo_exc:
                raise RuntimeError(f'RELEASE_REPOSITORY_ACCESS_FAILED: HTTP {repo_exc.code} for {repository}') from repo_exc
            if not isinstance(repo_info, dict) or repo_info.get('full_name','').lower() != repository.lower():
                raise RuntimeError('RELEASE_REPOSITORY_IDENTITY_MISMATCH: cannot verify target repository')
            return False
        raise RuntimeError(f'RELEASE_PROBE_API_FAILED: HTTP {exc.code} checking {tag}; check token permissions, API access, or rate limits') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('RELEASE_PROBE_NETWORK_FAILED: ' + str(exc.reason)) from exc
    if not isinstance(release, dict) or release.get('tag_name') != tag:
        raise RuntimeError('RELEASE_PROBE_RESPONSE_INVALID: response tag does not match requested release')
    return True


def probe(mode, repository, tag, token, output_file=None):
    found = release_exists(repository, tag, token)
    if mode == 'skip':
        if found:
            print(f'RELEASE_ALREADY_EXISTS: {tag}; skipping duplicate production build.')
        else:
            print(f'RELEASE_NOT_FOUND: {tag}; safe to proceed with build.')
        if output_file:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write('skip=' + ('true' if found else 'false') + '\n')
    elif mode == 'guard':
        if found:
            raise RuntimeError(f'PRODUCTION_RELEASE_ALREADY_EXISTS: {tag}; refusing overwrite.')
        print(f'RELEASE_NOT_FOUND: {tag}; safe to proceed with packaging.')
    else:
        raise RuntimeError('RELEASE_PROBE_MODE_INVALID')
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--mode', choices=('skip','guard'), required=True)
    args = parser.parse_args()
    probe(args.mode, args.repository, args.tag,
          os.environ.get('GITHUB_TOKEN',''), os.environ.get('GITHUB_OUTPUT',''))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('RELEASE_EXISTENCE_CHECK_FAILED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
