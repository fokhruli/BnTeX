"""Validate early private-publication safety with a mocked gh (no network)."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def test_publisher_shell_syntax():
    assert subprocess.run(['bash','-n',str(ROOT/'tools/publish_private.sh')]).returncode==0

def test_publisher_rejects_wrong_account_before_git_writes(tmp_path):
    repo=tmp_path/'project';(repo/'tools').mkdir(parents=True)
    shutil.copyfile(ROOT/'tools/publish_private.sh',repo/'tools/publish_private.sh')
    tools=tmp_path/'bin';tools.mkdir()
    gh=tools/'gh'
    gh.write_text('#!/bin/sh\ncase "$1" in auth) exit 0;; api) echo different-user;; *) exit 99;; esac\n')
    gh.chmod(0o755)
    env=dict(os.environ,PATH=str(tools)+os.pathsep+os.environ['PATH'])
    p=subprocess.run(['bash',str(repo/'tools/publish_private.sh')],cwd=repo,env=env,capture_output=True,text=True)
    assert p.returncode!=0 and 'expected fokhruli' in p.stderr
    assert not (repo/'.git').exists()
