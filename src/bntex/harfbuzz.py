"""Small, ownership-safe adapter to HarfBuzz's public C API.

Cluster indices are UTF-8 byte offsets, never Python character indices.
No font file, executable, or shared library is downloaded by this module.
"""
from __future__ import annotations
import ctypes as C
import ctypes.util
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Glyph:
    gid: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int
    flags: int


class _Info(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ('codepoint', 'mask', 'cluster', 'var1', 'var2')]


class _Position(C.Structure):
    _fields_ = [('x_advance', C.c_int32), ('y_advance', C.c_int32),
                ('x_offset', C.c_int32), ('y_offset', C.c_int32), ('var', C.c_uint32)]


class HarfBuzz:
    """One static font face. Use as a context manager; not thread-safe."""
    def __init__(self, font_path: str | Path):
        self._font = self._face = self._blob = None
        name = ctypes.util.find_library('harfbuzz')
        if not name:
            raise RuntimeError('libharfbuzz is required for preparation, not pdfLaTeX. '
                               'Install libharfbuzz0b on Debian/Ubuntu or harfbuzz with Homebrew.')
        self._lib = L = C.CDLL(name)
        def bind(n, result, *args):
            fn = getattr(L, n); fn.restype = result; fn.argtypes = list(args)
        p, u, i, s = C.c_void_p, C.c_uint, C.c_int, C.c_char_p
        bind('hb_version_string', s)
        bind('hb_blob_create', p, s, u, i, p, p)
        bind('hb_blob_destroy', None, p)
        bind('hb_face_create', p, p, u)
        bind('hb_face_destroy', None, p)
        bind('hb_face_get_upem', u, p)
        bind('hb_face_get_glyph_count', u, p)
        bind('hb_font_create', p, p)
        bind('hb_font_destroy', None, p)
        bind('hb_ot_font_set_funcs', None, p)
        bind('hb_font_set_scale', None, p, i, i)
        bind('hb_buffer_create', p)
        bind('hb_buffer_destroy', None, p)
        bind('hb_buffer_allocation_successful', i, p)
        bind('hb_buffer_add_utf8', None, p, s, i, u, i)
        bind('hb_buffer_set_direction', None, p, i)
        bind('hb_script_from_string', C.c_uint32, s, i)
        bind('hb_buffer_set_script', None, p, C.c_uint32)
        bind('hb_language_from_string', p, s, i)
        bind('hb_buffer_set_language', None, p, p)
        bind('hb_buffer_set_cluster_level', None, p, i)
        bind('hb_shape', None, p, p, p, u)
        bind('hb_buffer_get_glyph_infos', C.POINTER(_Info), p, C.POINTER(u))
        bind('hb_buffer_get_glyph_positions', C.POINTER(_Position), p, C.POINTER(u))
        bind('hb_glyph_info_get_glyph_flags', u, C.POINTER(_Info))
        data = Path(font_path).read_bytes()
        if not data or len(data) > 64 * 1024 * 1024:
            raise ValueError('Font must be nonempty and smaller than 64 MiB.')
        # HB_MEMORY_MODE_DUPLICATE=0: HarfBuzz owns a copy of these bytes.
        self._blob = L.hb_blob_create(data, len(data), 0, None, None)
        self._face = L.hb_face_create(self._blob, 0)
        if not L.hb_face_get_glyph_count(self._face):
            self.close(); raise ValueError('HarfBuzz could not load the font face.')
        self.upem = int(L.hb_face_get_upem(self._face))
        self._font = L.hb_font_create(self._face)
        L.hb_ot_font_set_funcs(self._font)
        L.hb_font_set_scale(self._font, self.upem, self.upem)
        self.version = L.hb_version_string().decode('ascii')

    def shape(self, text: str, *, script: str = 'Beng', language: str = 'bn') -> list[Glyph]:
        if self._font is None:
            raise RuntimeError('HarfBuzz font has been closed.')
        if not text or len(text) > 4096 or '\x00' in text:
            raise ValueError('A shaping run must contain 1..4096 non-NUL characters.')
        raw = text.encode('utf-8', errors='strict')
        L = self._lib
        buf = L.hb_buffer_create()
        try:
            L.hb_buffer_add_utf8(buf, raw, len(raw), 0, len(raw))
            L.hb_buffer_set_direction(buf, 4)  # HB_DIRECTION_LTR
            L.hb_buffer_set_script(buf, L.hb_script_from_string(script.encode('ascii'), -1))
            L.hb_buffer_set_language(buf, L.hb_language_from_string(language.encode('ascii'), -1))
            L.hb_buffer_set_cluster_level(buf, 0)  # MONOTONE_GRAPHEMES
            L.hb_shape(self._font, buf, None, 0)
            if not L.hb_buffer_allocation_successful(buf):
                raise MemoryError('HarfBuzz buffer allocation failed.')
            n = C.c_uint(); m = C.c_uint()
            infos = L.hb_buffer_get_glyph_infos(buf, C.byref(n))
            pos = L.hb_buffer_get_glyph_positions(buf, C.byref(m))
            if n.value != m.value:
                raise RuntimeError('HarfBuzz returned inconsistent arrays.')
            result = []
            for j in range(n.value):
                g, q = infos[j], pos[j]
                flags = int(L.hb_glyph_info_get_glyph_flags(C.byref(infos[j])))
                result.append(Glyph(int(g.codepoint), int(g.cluster), q.x_advance,
                                    q.y_advance, q.x_offset, q.y_offset, flags))
            if any(g.gid == 0 for g in result):
                raise ValueError(f'Font has a missing glyph while shaping {text!r}.')
            if any(g.y_advance != 0 for g in result):
                raise ValueError('Vertical advances are outside the horizontal Bengali profile.')
            return result
        finally:
            L.hb_buffer_destroy(buf)

    def close(self):
        for attr, destroy in (('_font', 'hb_font_destroy'), ('_face', 'hb_face_destroy'),
                              ('_blob', 'hb_blob_destroy')):
            obj = getattr(self, attr, None)
            if obj:
                getattr(self._lib, destroy)(obj); setattr(self, attr, None)

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, traceback): self.close()
