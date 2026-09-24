"""Conservative literal-span scanner with source locations; not a TeX parser."""
from __future__ import annotations

import re
from dataclasses import dataclass


class SourceError(ValueError):
    """An error located in decoded source (1-based Unicode scalar column)."""

    def __init__(self, message: str, source: str, offset: int, filename: str = '<string>'):
        self.filename = str(filename)
        self.offset = max(0, min(offset, len(source)))
        self.line = source.count('\n', 0, self.offset) + 1
        start = source.rfind('\n', 0, self.offset) + 1
        self.column = self.offset - start + 1
        end = source.find('\n', self.offset)
        end = len(source) if end < 0 else end
        # Bound the diagnostic, and prevent terminal control characters from being printed.
        left = max(start, self.offset - 60)
        right = min(end, left + 140)
        def safe(s: str) -> str:
            return ''.join(c if c.isprintable() else repr(c)[1:-1] for c in s)
        self.excerpt = ('...' if left > start else '') + safe(source[left:right])
        prefix = ('...' if left > start else '') + safe(source[left:self.offset])
        super().__init__(f'{self.filename}:{self.line}:{self.column}: {message}\n'
                         f'  {self.excerpt}\n  {" " * len(prefix)}^')


class TextError(ValueError):
    """A validation error relative to a span, before attaching a source name."""

    def __init__(self, message: str, offset: int = 0):
        self.offset = offset
        super().__init__(message)


@dataclass(frozen=True)
class Span:
    text: str
    style: str
    offset: int


VERBATIM = {'verbatim', 'verbatim*', 'Verbatim', 'lstlisting', 'minted', 'comment'}
STYLE = re.compile(r'[a-z][a-z0-9-]{0,31}\Z')
COMMAND = re.compile(r'\\([A-Za-z@]+|.)', re.S)
TOKEN = re.compile(r'\\([A-Za-z@]+|.)|.', re.S)
ENVIRONMENT = re.compile(r'\s*\{([^{}]+)\}')


def words(text: str) -> list[str]:
    """Preserve original Unicode; normalize only TeX-like ASCII whitespace."""
    blank = re.search(r'\n[ \t\r]*\n', text)
    if blank:
        raise TextError('Blank paragraphs inside \\bn are unsupported; use separate spans.', blank.start())
    for i, c in enumerate(text):
        if c in '\\{}$&#%^_~':
            raise TextError('\\bn accepts literal text only; put TeX commands and math outside it.', i)
        if c.isspace() and c not in ' \t\r\n':
            raise TextError('Only ordinary ASCII whitespace is supported in \\bn spans.', i)
        if (ord(c) < 32 and c not in '\t\r\n') or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF:
            raise TextError('Invalid Unicode or control character in Bengali text.', i)
    return [w for w in re.split(r'[ \t\r\n]+', text.strip(' \t\r\n')) if w]


def scan(source: str, *, filename: str = '<string>') -> list[Span]:
    """Skip comments, \\verb, and common verbatim environments.

    Does not expand macros, evaluate conditionals, follow \\input, or interpret
    catcode changes. All offsets refer to the original decoded source.
    """
    found: list[Span] = []
    i = 0
    def error(message: str, offset: int) -> SourceError:
        return SourceError(message, source, offset, filename)
    while i < len(source):
        if source[i] == '%':
            end = source.find('\n', i)
            i = len(source) if end < 0 else end + 1
            continue
        if source[i] != '\\':
            i += 1
            continue
        start = i
        m = COMMAND.match(source, i)
        if not m:
            i += 1
            continue
        name = m.group(1)
        i = m.end()
        if name in {'string', 'meaning'}:
            while i < len(source) and source[i] in ' \t\r\n':
                i += 1
            token = TOKEN.match(source, i)
            if token:
                i = token.end()
            continue
        if name == 'verb':
            if i < len(source) and source[i] == '*':
                i += 1
            if i >= len(source):
                raise error('Unterminated \\verb.', start)
            delim = source[i]
            end = source.find(delim, i + 1)
            if end < 0:
                raise error('Unterminated \\verb.', start)
            i = end + 1
            continue
        if name == 'begin':
            env = ENVIRONMENT.match(source, i)
            if env and env.group(1) in VERBATIM:
                closer = '\\end{' + env.group(1) + '}'
                end = source.find(closer, env.end())
                if end < 0:
                    raise error(f'Unterminated {env.group(1)} environment.', start)
                i = end + len(closer)
                continue
        if name != 'bn':
            continue
        while i < len(source) and source[i] in ' \t\r\n':
            i += 1
        style = 'auto'
        if i < len(source) and source[i] == '[':
            end = source.find(']', i + 1)
            if end < 0:
                raise error('Unterminated \\bn option.', start)
            style = source[i + 1:end]
            if not STYLE.fullmatch(style):
                raise error(f'Invalid style {style!r}.', i + 1)
            i = end + 1
            while i < len(source) and source[i] in ' \t\r\n':
                i += 1
        if i >= len(source) or source[i] != '{':
            raise error('Expected literal braced text after \\bn.', start)
        end = source.find('}', i + 1)
        if end < 0:
            raise error('Unterminated \\bn.', start)
        text = source[i + 1:end]
        try:
            words(text)
        except TextError as exc:
            raise error(str(exc), i + 1 + exc.offset) from exc
        found.append(Span(text, style, start))
        i = end + 1
    return found
