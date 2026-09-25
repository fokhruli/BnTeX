#!/usr/bin/env python3
"""One explicitly requested cleanup; dry-run unless --apply is supplied.

Only exact allowlisted tips already in main are eligible. Open-PR head/base refs,
protected/default branches, changed tips and non-ancestors are preserved. Atomic
lease-guarded ref deletions prevent deleting concurrently advanced branches.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

REPOSITORY = 'fokhruli/BnTeX'
SHA = re.compile(r'[0-9a-f]{40}\Z')
BRANCH = re.compile(r'(?:feat|chore|copilot)/[a-z0-9][a-z0-9-]{0,80}\Z')


def validate_request(data):
    if not isinstance(data, dict) or set(data) != {'schema','repository','based_on_main','branches'}:
        raise ValueError('invalid cleanup request fields')
    if type(data['schema']) is not int or data['schema'] != 1 or data['repository'] != REPOSITORY:
        raise ValueError('wrong cleanup schema/repository')
    if not isinstance(data['based_on_main'], str) or not SHA.fullmatch(data['based_on_main']):
        raise ValueError('invalid main checkpoint')
    rows = data['branches']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
        raise ValueError('expected 1..32 explicit branch candidates')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'name','sha'}:
            raise ValueError('invalid branch record')
        name, sha = row['name'], row['sha']
        if not isinstance(name, str) or not BRANCH.fullmatch(name) or name in seen:
            raise ValueError('invalid or duplicate branch name')
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError('invalid branch tip')
        seen.add(name)
    return data


def plan(request, current, pulls, is_ancestor):
    """Pure decision layer: no API mutations, no inferred candidate branches."""
    validate_request(request)
    active = {pr[side]['ref'] for pr in pulls for side in ('head','base')
              if isinstance(pr.get(side), dict) and isinstance(pr[side].get('ref'), str)}
    result = []
    for candidate in request['branches']:
        name, tip = candidate['name'], candidate['sha']
        live = current.get(name)
        if live is None:
            reason = 'absent'
        elif live['protected']:
            reason = 'protected'
        elif live['sha'] != tip:
            reason = 'tip-changed'
        elif name in active:
            reason = 'open-pr-dependency'
        elif not is_ancestor(tip):
            reason = 'not-ancestor-of-main'
        else:
            reason = 'eligible'
        result.append(dict(candidate, decision=reason))
    return result


def deletion_command(rows):
    selected = [r for r in rows if r['decision'] == 'eligible']
    if not selected:
        return []
    # Validate even this internal boundary; never accept arbitrary refspecs.
    for row in selected:
        if not BRANCH.fullmatch(row['name']) or not SHA.fullmatch(row['sha']):
            raise ValueError('unsafe deletion record')
    return ['git','push','--atomic',
            *(f"--force-with-lease=refs/heads/{r['name']}:{r['sha']}" for r in selected),
            'origin', *(f":refs/heads/{r['name']}" for r in selected)]


class GitHubRead:
    def __init__(self, token):
        self.token = token

    def get(self, suffix):
        req = urllib.request.Request(f'https://api.github.com/repos/{REPOSITORY}/{suffix}',
              headers={'Authorization':f'Bearer {self.token}', 'Accept':'application/vnd.github+json',
                       'X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('oversized API response')
        return json.loads(raw)

    def pages(self, endpoint):
        result = []
        for page in range(1, 21):
            chunk = self.get(f'{endpoint}&per_page=100&page={page}')
            if not isinstance(chunk, list):
                raise ValueError('invalid API collection')
            result.extend(chunk)
            if len(chunk) < 100:
                return result
        raise ValueError('API collection exceeds cleanup limit')

    def snapshot(self):
        repo = self.get('')
        if repo.get('full_name') != REPOSITORY or repo.get('default_branch') != 'main' or repo.get('private') is not True:
            raise ValueError('repository/default/privacy guard failed')
        rows = self.pages('branches?')
        branches = {b['name']: {'sha': b['commit']['sha'], 'protected':b['protected']} for b in rows}
        return branches, self.pages('pulls?state=open')


def git(args, env, check=True):
    return subprocess.run(['git',*args], env=env, text=True, capture_output=True,
                          check=check, timeout=90)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.request.is_symlink() or args.request.stat().st_size > 16384 or args.out.exists():
        raise ValueError('unsafe request or existing output')
    request = validate_request(json.loads(args.request.read_text()))
    token = os.environ.get('GH_TOKEN', '')
    expected = os.environ.get('GITHUB_SHA', '')
    if (not token or os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
            or os.environ.get('GITHUB_REF') != 'refs/heads/main' or not SHA.fullmatch(expected)):
        raise ValueError('requires an authorized main-branch Actions run')
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
               GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode())
    remote = git(['remote','get-url','origin'], env).stdout.strip().removesuffix('.git')
    if remote != 'https://github.com/'+REPOSITORY:
        raise ValueError('unexpected Git remote')
    api = GitHubRead(token)
    git(['fetch','--no-tags','origin','+refs/heads/*:refs/remotes/origin/*'], env)
    if git(['rev-parse','HEAD'],env).stdout.strip() != expected:
        raise ValueError('checkout differs from requested main run')
    def ancestor(tip):
        code = git(['merge-base','--is-ancestor',tip,expected],env,check=False).returncode
        if code not in (0,1):
            raise ValueError('cannot establish branch ancestry')
        return code == 0
    if not ancestor(request['based_on_main']):
        raise ValueError('main checkpoint not retained')
    branches, pulls = api.snapshot()
    if branches.get('main',{}).get('sha') != expected:
        raise ValueError('main moved; rerun from current main after review')
    decisions = plan(request, branches, pulls, ancestor)
    applied = []
    if args.apply:
        fresh, active = api.snapshot()
        if fresh.get('main',{}).get('sha') != expected or plan(request,fresh,active,ancestor) != decisions:
            raise ValueError('cleanup plan changed during validation')
        command = deletion_command(decisions)
        if command:
            # Do not print auth environment or dump subprocess exceptions containing it.
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
            if run.returncode:
                raise ValueError('atomic lease-guarded delete failed; no retry or force fallback')
            applied = [r['name'] for r in decisions if r['decision'] == 'eligible']
        after, _ = api.snapshot()
        if any(name in after for name in applied):
            raise ValueError('deletion verification failed')
    report = {'schema':1,'repository':REPOSITORY,'main':expected,'apply':args.apply,
              'decisions':decisions,'deleted':applied}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x') as handle:
        json.dump(report,handle,indent=2); handle.write('\n')
    print(json.dumps(report,indent=2))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as handle:
            handle.write('# Verified merged-branch cleanup\n\n'+
                         '\n'.join(f"- `{r['name']}`: {r['decision']} ({r['sha']})" for r in decisions)+
                         '\n\nDeleted: '+str(len(applied))+'. No main reset or issue deletion.\n')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Report bounded diagnostics, never request headers or the authentication environment.
        print('Branch cleanup stopped: '+str(exc)[:240],file=sys.stderr)
        raise SystemExit(1)
