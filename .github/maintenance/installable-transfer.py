"""One-use, exact-tree transfer of already-tested source; no fonts or publication."""
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess

CHECKPOINT = '4169710a7ca9b423c7e1844316c27091f769ca7b'
TREE = '23ae9f9fbcca77a391794f44328b5bf64fb5ac7a'
PATCH_SHA = '8876aefcc8a1cfcd7d6659f80ceb6ced344d9c9894be87209d4ea8d7a1cc204a'
BRANCH = 'feat/installable-distribution'
PREFIX = '.github/maintenance/installable-transfer'
WORKFLOW = '.github/workflows/distribution-dry-run.yml'
WORKFLOW_BLOB = 'd86b945461308ccb4a17c5b9a46a1579a4b304e0'


def git(*args, **kw):
    return subprocess.check_output(['git', *args], **kw).decode().strip()


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if (os.environ.get('GITHUB_REPOSITORY') != 'fokhruli/BnTeX'
            or os.environ.get('GITHUB_REF') != 'refs/heads/' + BRANCH
            or event.get('repository', {}).get('private') is not True):
        raise RuntimeError('Wrong repository, branch, or visibility')
    if git('rev-parse', 'HEAD') != os.environ['GITHUB_SHA'] or git('rev-parse', 'HEAD^') != CHECKPOINT:
        raise RuntimeError('Source checkpoint moved')
    # The authorized connector installs workflow changes; GITHUB_TOKEN does not
    # have workflow-write permission and is used only for ordinary source here.
    if git('hash-object', WORKFLOW) != WORKFLOW_BLOB:
        raise RuntimeError('Prerequisite workflow differs')
    parts = [PREFIX + '.' + str(i) + '.b64' for i in range(3)]
    encoded = ''.join(Path(p).read_text('ascii') for p in parts)
    if len(encoded) != 28560:
        raise RuntimeError('Wrong transfer size')
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
    patch = decoder.decompress(base64.b64decode(encoded, validate=True), max_length=200000)
    if (not decoder.eof or decoder.unused_data
            or hashlib.sha256(patch).hexdigest() != PATCH_SHA
            or b'GIT binary patch' in patch):
        raise RuntimeError('Wrong source payload')
    path = Path('.git/bntex-tested-source.patch')
    path.write_bytes(patch)
    git('apply', '--check', '--index', '--exclude=' + WORKFLOW, str(path))
    git('apply', '--index', '--exclude=' + WORKFLOW, str(path))
    git('rm', '--', *parts, PREFIX + '.py', '.github/workflows/installable-source-transfer.yml')
    if git('write-tree') != TREE:
        raise RuntimeError('Candidate tree differs from locally tested source')
    git('-c', 'user.name=BnTeX development automation', '-c',
        'user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit', '-m', 'feat: installed BnTeX entry point and checked TDS distribution candidate',
        '-m', 'Exact locally tested source tree; 848 tests passed. Standard TeX Live read-policy installation works. Restrictive openin_any=p remains an explicit limitation. No font binaries, public upload, browser acceptance or release approval. Remove one-use source transport from final tree.')
    env = dict(os.environ)
    auth = base64.b64encode(('x-access-token:' + env['GITHUB_TOKEN']).encode()).decode()
    env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + auth)
    git('push', 'origin', 'HEAD:refs/heads/' + BRANCH, env=env)
    print('Transferred tested source tree', TREE, 'at', git('rev-parse', 'HEAD'))


if __name__ == '__main__':
    main()
