"""Private packaging checks are independent of font/rendering acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_preflight',ROOT/'tools/release_preflight.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def gate_data():
    return {'schema':1,'purpose':'private-release-readiness','gates':[
        {'id':key,'status':'pending','evidence':None,'detail':'Requires actual evidence.'}
        for key in sorted(r.GATES)]}


def cmd(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE)


def commit(root):
    cmd(root,'add','.');cmd(root,'commit','-qm','test fixture')


@pytest.fixture
def repo(tmp_path):
    root=tmp_path/'repo';root.mkdir();cmd(root,'init','-q')
    cmd(root,'config','user.name','Packaging Test');cmd(root,'config','user.email','test@example.invalid')
    for name in r.REQUIRED:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Test fixture\n')
    (root/'docs/RELEASE-READINESS.json').write_text(json.dumps(gate_data()))
    for name in ('tex/latex/bntex/bntex-native.sty','src/bntex/data/bntex-native.sty'):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('% same source\n')
    commit(root);return root


def test_pending_release_is_not_passed():
    report=r.readiness(json.dumps(gate_data()).encode())
    assert not report['recorded_gates_complete'] and set(report['blockers'])==r.GATES


@pytest.mark.parametrize('fault',['schema','purpose','missing','duplicate','unknown','status','detail','evidence'])
def test_bad_gate_records_fail(fault):
    data=gate_data()
    if fault=='schema':data['schema']=True
    if fault=='purpose':data['purpose']='publish-now'
    if fault=='missing':data['gates'].pop()
    if fault=='duplicate':data['gates'].append(copy.deepcopy(data['gates'][0]))
    if fault=='unknown':data['gates'][0]['id']='invented'
    if fault=='status':data['gates'][0]['status']='maybe'
    if fault=='detail':data['gates'][0]['detail']=''
    if fault=='evidence':data['gates'][0]['status']='passed'
    with pytest.raises(ValueError):r.readiness(json.dumps(data).encode())


def test_recorded_evidence_not_authenticated():
    data=gate_data()
    for gate in data['gates']:gate.update(status='passed',evidence='review-record')
    report=r.readiness(json.dumps(data).encode())
    assert report['recorded_gates_complete']
    assert 'not performed' in report['evidence_authentication']


def test_duplicate_json_keys_fail():
    with pytest.raises(ValueError):r.readiness(b'{"schema":1,"schema":1}')


@pytest.mark.parametrize('fault',['font','renamed-font','private-key','resource','dirty','missing','symlink','case','compressed','archive'])
def test_source_audit_rejections(repo,fault):
    p=repo/'new.txt'
    if fault=='font':p=repo/'bad.ttf';p.write_bytes(b'font')
    if fault=='renamed-font':p.write_bytes(bytes([0,1,0,0])+b'font')
    if fault=='private-key':p.write_text('-----BEGIN '+'PRIVATE KEY-----')
    if fault=='resource':(repo/'src/bntex/data/bntex-native.sty').write_text('mismatch')
    if fault=='dirty':(repo/'README.md').write_text('dirty')
    if fault=='missing':(repo/'LICENSE').unlink()
    if fault=='symlink':p.symlink_to(repo/'README.md')
    if fault=='case':(repo/'readme.md').write_text('collision')
    if fault=='compressed':(repo/'data.gz').write_bytes(b'compressed')
    if fault=='archive':(repo/'secret.zip').write_bytes(b'zip')
    if fault!='dirty':commit(repo)
    with pytest.raises(ValueError):r.collect(repo)


def test_deterministic_private_archive_excludes_untracked(repo,tmp_path):
    (repo/'untracked-secret.txt').write_text('not eligible')
    assets,report=r.collect(repo)
    assert report['mechanical_audit']=='passed' and report['tex_resource_pairs']==1
    assert 'untracked-secret.txt' not in assets
    manual=tmp_path/'manual.pdf';manual.write_bytes(b'%PDF-test fixture')
    a=tmp_path/'a.zip';b=tmp_path/'b.zip'
    assert r.archive(a,assets,report,manual)==r.archive(b,assets,report,manual)
    with zipfile.ZipFile(a) as z:
        assert 'bntex-source-review/docs/manual/bntex-manual.tex' in z.namelist()
        assert 'bntex-source-review/docs/manual/bntex-manual.pdf' in z.namelist()
        assert not any('untracked' in n for n in z.namelist())
    with pytest.raises(FileExistsError):r.archive(a,assets,report,manual)


def test_manual_must_be_pdf(repo,tmp_path):
    assets,report=r.collect(repo);manual=tmp_path/'bad';manual.write_text('not PDF')
    with pytest.raises(ValueError):r.archive(tmp_path/'x.zip',assets,report,manual)


def test_release_gate_cli_fails_closed_but_mechanical_mode_passes(repo,tmp_path):
    first=tmp_path/'first.json';second=tmp_path/'second.json'
    assert r.main(['--root',str(repo),'--out',str(first)])==0
    assert r.main(['--root',str(repo),'--out',str(second),'--require-ready'])==1
    assert json.loads(second.read_text())['public_upload_performed'] is False
    assert r.main(['--root',str(repo),'--out',str(first)])==2


def test_partial_archive_arguments_rejected(repo,tmp_path):
    out=tmp_path/'report.json'
    assert r.main(['--root',str(repo),'--out',str(out),'--archive',str(tmp_path/'x.zip')])==2
    assert not out.exists()
