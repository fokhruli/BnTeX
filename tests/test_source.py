from pathlib import Path
import unicodedata
import pytest
from bntex.source import scan, words
from bntex.build import tex_hash

@pytest.mark.parametrize('text,expected',[
 ('বাংলা ভাষা',['বাংলা','ভাষা']),
 ('  বাংলা\tভাষা\n স্বাস্থ্য  ',['বাংলা','ভাষা','স্বাস্থ্য']),
 ('ক্\u200dষ ক্\u200cষ',['ক্\u200dষ','ক্\u200cষ']),
 ('',[]),
])
def test_word_split(text,expected): assert words(text)==expected

@pytest.mark.parametrize('text',['x_y','\\foo','{x}','x$y','x%y','x~y','x&y','x^y','x#y',
 'x\n \ny','x\u00a0y','x\x00y','\ud800'])
def test_reject_unsupported(text):
    with pytest.raises(ValueError): words(text)

def test_comment_verb_and_environment_skip():
    source=r'''% \bn{bad}
\verb|\bn{bad}| \verb*+\bn{bad}+
\begin{verbatim}\bn{bad}\end{verbatim}
\begin{lstlisting}\bn{bad}\end{lstlisting}
\string\bn \meaning\bn
\bn{বাংলা ভাষা} \bn[bold]{স্বাস্থ্য}
'''
    spans=scan(source)
    assert [(x.text,x.style) for x in spans]==[('বাংলা ভাষা','auto'),('স্বাস্থ্য','bold')]

@pytest.mark.parametrize('source',[r'\bn',r'\bn[bold',r'\bn[../x]{a}',r'\bn{abc',r'\bn{a{b}}',
 r'\bn{a\emph{b}}',r'\verb|missing',r'\begin{verbatim}missing'])
def test_scanner_fail_closed(source):
    with pytest.raises(ValueError): scan(source)

def test_preserve_original_unicode():
    original='\u09dc'; decomposed=unicodedata.normalize('NFD',original)
    assert original!=decomposed
    assert words(original)==[original]
    assert tex_hash(original)!=tex_hash(decomposed)
    assert len(tex_hash('বাংলা'))==32

def test_package_resource_is_identical():
    root=Path(__file__).resolve().parents[1]
    assert (root/'tex/latex/bntex/bntex.sty').read_bytes()==(root/'src/bntex/data/bntex.sty').read_bytes()
