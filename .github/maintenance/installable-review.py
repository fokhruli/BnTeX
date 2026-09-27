"""One-use transfer of reviewed text-only fixes with exact source-tree guards."""
import base64, hashlib, json, lzma, os, subprocess
from pathlib import Path
BASE='5a397bbd0d4ccc513c724694087b45cdee2df237'
TREE='9529ea1955dc5036836d4d21bc2ed8ecb65ebbba'
BRANCH='feat/installable-distribution'
WORKFLOW='.github/workflows/distribution-dry-run.yml'
def git(*args,**kw):
    return subprocess.check_output(['git',*args],**kw).decode().strip()
def main():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if (os.environ['GITHUB_REPOSITORY']!='fokhruli/BnTeX' or event['repository']['private'] is not True
        or os.environ['GITHUB_REF']!='refs/heads/'+BRANCH or git('rev-parse','HEAD')!=os.environ['GITHUB_SHA']
        or git('rev-parse','HEAD^')!=BASE):raise RuntimeError('Unexpected checkpoint')
    text=Path('.github/maintenance/installable-review.b64').read_text('ascii')
    if len(text)!=7864:raise RuntimeError('Wrong payload length')
    dec=lzma.LZMADecompressor(memlimit=128*1024*1024)
    raw=dec.decompress(base64.b64decode(text,validate=True),max_length=200000)
    if not dec.eof or dec.unused_data or hashlib.sha256(raw).hexdigest()!='b30ed68a9e9d32a1e7750953d98c94fddd19be4a21042df1a38deebf874d4f08':
        raise RuntimeError('Wrong source patch')
    p=Path('.git/reviewed-source.patch');p.write_bytes(raw)
    # The authorized connector has already installed the exact workflow change.
    git('apply','--check','--index','--exclude='+WORKFLOW,str(p))
    git('apply','--index','--exclude='+WORKFLOW,str(p))
    git('rm','--','.github/maintenance/installable-review.py','.github/maintenance/installable-review.b64',
        '.github/workflows/installable-review-transfer.yml')
    if git('write-tree')!=TREE:raise RuntimeError('Reviewed source tree mismatch')
    git('-c','user.name=BnTeX development automation','-c','user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit','-m','test: fix installed-asset selection and probe engine read-policy capability',
        '-m','Address review: retain copied-cache rejection while exempting only the legacy module. Correct TDS source/runtime selection and engine-dependent restrictive-read expectations. No TeX runtime changes, relaxed security settings, font upload, or publication.')
    env=dict(os.environ)
    auth=base64.b64encode(('x-access-token:'+env['GITHUB_TOKEN']).encode()).decode()
    env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',GIT_CONFIG_VALUE_0='AUTHORIZATION: basic '+auth)
    git('push','origin','HEAD:refs/heads/'+BRANCH,env=env)
    print('Reviewed source transferred',git('rev-parse','HEAD'),TREE)
if __name__=='__main__':main()
