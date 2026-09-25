"""Regression for the first live cleanup's pre-mutation 404 failure."""
import pytest
from test_branch_cleanup import c

@pytest.mark.parametrize('suffix,expected',[
 ('','https://api.github.com/repos/fokhruli/BnTeX'),
 ('branches?per_page=100&page=1','https://api.github.com/repos/fokhruli/BnTeX/branches?per_page=100&page=1'),
])
def test_api_url_has_no_spurious_root_slash(monkeypatch,suffix,expected):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return b'{}'
    def opened(req,timeout):
        assert req.full_url==expected
        assert timeout==30
        return Response()
    monkeypatch.setattr(c.urllib.request,'urlopen',opened)
    assert c.GitHubRead('test-placeholder').get(suffix)=={}

@pytest.mark.parametrize('endpoint,expected',[
 ('branches','branches?per_page=100&page=1'),
 ('pulls?state=open','pulls?state=open&per_page=100&page=1'),
])
def test_collection_query_separator(monkeypatch,endpoint,expected):
    api=c.GitHubRead('test-placeholder');calls=[]
    monkeypatch.setattr(api,'get',lambda path:calls.append(path) or [])
    assert api.pages(endpoint)==[] and calls==[expected]
