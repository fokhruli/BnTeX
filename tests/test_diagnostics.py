from pathlib import Path
import pytest
from bntex.source import SourceError, scan
from bntex.__main__ import main


@pytest.mark.parametrize('source,line,column', [
    ('% ignored \\bn{bad}\n\\bn{বাংলা_ভাষা}', 2, 10),
    ('বাংলা \\bn', 1, 7),
    ('first\n\\bn{ক\nখ$}', 3, 2),
    ('\\bn[../x]{ক}', 1, 5),
    ('\\verb|unterminated', 1, 1),
    ('\\begin{verbatim}x', 1, 1),
])
def test_source_location(source, line, column):
    with pytest.raises(SourceError) as result:
        scan(source, filename='chapter.tex')
    error = result.value
    assert (error.filename, error.line, error.column) == ('chapter.tex', line, column)
    assert f'chapter.tex:{line}:{column}:' in str(error)
    assert '^' in str(error)


def test_scan_preserves_offsets_after_verbatim():
    source = '% comment\n\\verb|\\bn{bad}|\n  \\bn{ক}'
    assert scan(source)[0].offset == source.rfind('\\bn')


def test_excerpt_is_bounded_and_control_safe():
    with pytest.raises(SourceError) as result:
        scan('\\bn{' + 'ক' * 500 + '\x1b' + 'ক' * 500 + '}')
    assert len(result.value.excerpt) < 160
    assert '\x1b' not in str(result.value)
    assert '\\x1b' in str(result.value)


@pytest.mark.integration
@pytest.mark.parametrize('raw,expected', [
    (b'hello\n\\bn{\xff}', ':2:5: Invalid UTF-8'),
    ('% comment\n\\bn[missing]{ক}'.encode(), ':2:1: Unprepared style'),
    ('\\bn{ক_খ}'.encode(), ':1:6:'),
])
def test_cli_source_failure(tmp_path, fonts, tex_tools, capsys, raw, expected):
    path = tmp_path / 'input.tex'
    path.write_bytes(raw)
    result = main(['prepare', '--source', str(path), '--font', 'regular=' + str(fonts['regular']),
                   '--out', str(tmp_path / 'output')])
    assert result == 2
    error = capsys.readouterr().err
    assert str(path) + expected in error
    assert 'Traceback' not in error
    assert not (tmp_path / 'output').exists()
