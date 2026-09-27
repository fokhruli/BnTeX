"""Independent, traceable Bengali bng2 shaping over a typed font profile.

Python model for a later expl3 port, NOT a TeX-native shaper. No HarfBuzz,
FontTools, ctypes, subprocess, network or word-cache dependency at runtime.
The Bengali-only grammar/reordering follows the documented Indic model and
HarfBuzz 10.2.0's open implementation; attribution: THIRD-PARTY-NOTICES.md.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import re
import unicodedata as ud
from .native_profile import FontProfile, validate, serialize
from .native_layout import Buffer, Item, Layout, ShapingError

# Ordered placement classes, not font glyph IDs.
START, REPH, PRE_M, PRE_C, BASE, AFTER_MAIN, ABOVE, BEFORE_SUB, BELOW, AFTER_SUB, BEFORE_POST, POST, AFTER_POST, FINAL, SMVD, END = range(16)
BASIC = ('nukt', 'akhn', 'rphf', 'rkrf', 'pref', 'blwf', 'abvf', 'half', 'pstf', 'vatu', 'cjct')
PRESENTATION = ('init', 'pres', 'abvs', 'blws', 'psts', 'haln', 'rclt', 'calt', 'clig', 'rlig')
SUPPORTED_FEATURES = set(('locl', 'ccmp') + BASIC + PRESENTATION)
MAX_INPUT_BYTES = 4096
MAX_SYLLABLE_SCALARS = 64
PINNED_PROFILE_SHA256 = 'f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42'


@dataclass(frozen=True, slots=True)
class Glyph:
    gid: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int
    flags: int


@dataclass(frozen=True, slots=True)
class DecodedInput:
    scalars: tuple[int, ...]
    byte_offsets: tuple[int, ...]
    byte_lengths: tuple[int, ...]
    utf8_hex: str

    @classmethod
    def from_text(cls, text: str):
        if not isinstance(text, str): raise ShapingError('input: expected Unicode text')
        if not text or len(text) > MAX_INPUT_BYTES:
            raise ShapingError('input: empty or oversized text')
        offsets, lengths, cursor = [], [], 0
        try:
            for c in text:
                offsets.append(cursor); size = len(c.encode('utf-8')); lengths.append(size); cursor += size
            raw = text.encode('utf-8')
            if len(raw) > MAX_INPUT_BYTES: raise ShapingError('input: text exceeds 4096 bytes')
        except UnicodeError as exc:
            raise ShapingError('input: non-scalar Unicode') from exc
        return cls(tuple(map(ord, text)), tuple(offsets), tuple(lengths), raw.hex())

    def text(self) -> str:
        if not all(isinstance(v, (tuple, list)) for v in (self.scalars, self.byte_offsets, self.byte_lengths)):
            raise ShapingError('input: decoded mappings must be arrays')
        if not (len(self.scalars) == len(self.byte_offsets) == len(self.byte_lengths)):
            raise ShapingError('input: decoded mapping arrays differ in length')
        if not self.scalars or len(self.scalars) > MAX_INPUT_BYTES:
            raise ShapingError('input: empty or oversized scalar sequence')
        if not isinstance(self.utf8_hex, str) or len(self.utf8_hex) > MAX_INPUT_BYTES * 2 or not re.fullmatch(r'(?:[0-9a-fA-F]{2})+', self.utf8_hex):
            raise ShapingError('input: invalid or oversized byte-hex transport')
        cursor, chars = 0, []
        for cp, offset, size in zip(self.scalars, self.byte_offsets, self.byte_lengths):
            if type(cp) is not int or not 0 <= cp <= 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
                raise ShapingError('input: invalid Unicode scalar')
            c = chr(cp); n = len(c.encode('utf-8'))
            if type(offset) is not int or type(size) is not int or offset != cursor or size != n:
                raise ShapingError('input: invalid scalar-to-byte mapping')
            chars.append(c); cursor += n
        text = ''.join(chars)
        if text.encode('utf-8').hex() != self.utf8_hex.lower():
            raise ShapingError('input: scalar/byte provenance mismatch')
        return text


@dataclass(frozen=True, slots=True)
class ShapeResult:
    text: str
    utf8_hex: str
    font_sha256: str
    profile_sha256: str
    glyphs: tuple[Glyph, ...]
    trace: tuple[dict, ...]
    operations: int

    def to_dict(self): return asdict(self)


# Bengali table categories cross-checked against the pinned reference's
# Unicode-16 property projection. No font-dependent classifications live here.
_CONSONANTS = set(range(0x995, 0x9A9)) | set(range(0x9AA, 0x9B1)) | {0x9B2, 0x9B6, 0x9B7, 0x9B8, 0x9B9, 0x9CE, 0x9DC, 0x9DD, 0x9DF, 0x9F0, 0x9F1}
_VOWELS = set(range(0x985, 0x98D)) | {0x98F, 0x990, 0x993, 0x994, 0x9E0, 0x9E1}
_PRE = {0x9BF, 0x9C7, 0x9C8}
_BELOW_MATRAS = {0x9C1, 0x9C2, 0x9C3, 0x9C4, 0x9E2, 0x9E3}
_POST_MATRAS = {0x9BE, 0x9C0, 0x9CB, 0x9CC, 0x9D7}


def properties(cp: int):
    if cp in (0x9B0, 0x9F0): return 'R', BASE
    if cp in _CONSONANTS: return 'C', BASE
    if cp in _VOWELS: return 'V', BASE
    if cp in _PRE: return 'M', PRE_M
    if cp in _BELOW_MATRAS: return 'M', AFTER_SUB
    if cp in _POST_MATRAS: return 'M', AFTER_POST
    if cp == 0x9CD: return 'H', BELOW
    if cp == 0x9BC: return 'N', END
    if cp in (0x981, 0x982, 0x983, 0x9FE): return 'S', SMVD
    if cp == 0x9BD: return 'Y', SMVD
    if cp in (0x200C, 0x200D): return ('n' if cp == 0x200C else 'j'), END
    if cp == 0x25CC: return 'D', BASE
    if cp in (0x980, 0x9FC, 0xA0, 0x2D) or 0x9E6 <= cp <= 0x9EF or 0x30 <= cp <= 0x39: return 'P', BASE
    return 'X', END


# Longest-prefix orthographic segmentation, a Bengali-only projection of the
# published Indic grammar. Every repeated term consumes a nonempty sequence;
# input length is bounded before matching. ZWNJ following virama terminates a
# consonant syllable; it is not silently stripped.
_C = r'[CR]j?N{0,2}'
_H = r'[jn]?H(?:jN?)?'
_M = r'[jn]*MN?H?'
_TAIL = rf'(?:{_H}{_C})*(?:{_H}|Hn|(?:{_M})*)(?:[jn]?SS?n?)?'
_PATTERNS = (
    ('consonant', re.compile(rf'{_C}{_TAIL}')),
    ('vowel', re.compile(rf'(?:RH)?VN{{0,2}}(?:j|{_TAIL})')),
    ('standalone', re.compile(rf'(?:P|(?:RH)?D)N{{0,2}}{_TAIL}')),
    ('symbol', re.compile(r'YN?(?:[jn]?SS?n?)?')),
    ('broken', re.compile(rf'(?:RH)?N{{0,2}}{_TAIL}')),
)


def syllables(items: list[Item]):
    cats = ''.join(g.category for g in items); cursor = 0; result = []
    while cursor < len(items):
        maximum = min(len(items), cursor + MAX_SYLLABLE_SCALARS + 1)
        best_end, best_kind = cursor + 1, 'other'
        for kind, pattern in _PATTERNS:
            # re's ordered alternatives need not return the longest alternative;
            # testing bounded full prefixes makes tie-breaking explicit.
            for end in range(maximum, cursor, -1):
                if end < best_end: break
                if pattern.fullmatch(cats, cursor, end):
                    if end > best_end or best_kind == 'other': best_end, best_kind = end, kind
                    break
        if best_end - cursor > MAX_SYLLABLE_SCALARS:
            raise ShapingError(f'syllables: more than {MAX_SYLLABLE_SCALARS} working scalars at byte {items[cursor].cluster}')
        result.append((cursor, best_end, best_kind)); cursor = best_end
    return result


class NativeShaper:
    """A fixed-font executable model; build once and reuse across unseen words."""
    def __init__(self, profile: FontProfile):
        self.profile = validate(profile)
        unknown = {f.tag for f in profile.gsub_features} - SUPPORTED_FEATURES
        if unknown: raise ShapingError(f'features: no runtime stage for {sorted(unknown)}')
        if {f.tag for f in profile.gpos_features} - {'dist', 'kern', 'abvm', 'blwm', 'mark', 'mkmk'}:
            raise ShapingError('features: unsupported positioning stage')
        if 'pref' in {f.tag for f in profile.gsub_features}:
            raise ShapingError('features: pre-base consonant reordering is outside this pinned font model')
        self.identity = hashlib.sha256(serialize(profile)).hexdigest()
        if self.identity not in (PINNED_PROFILE_SHA256,
                                 'e3a798be7b57bb363c041cb7252a97c2c565c59215db868e837c069ed117b0f8'):
            raise ShapingError('profile: compiled-rule fingerprint is not the supported ABI-1 profile')
        self.cmap = dict(profile.cmap)
        self.layout = Layout(profile)
        self.virama = self.cmap[0x9CD]
        self.dynamic_positions = {}
        for gid in set(self.cmap.values()):
            pairs = ((self.virama, gid), (gid, self.virama))
            if any(self.layout.would_substitute('blwf', seq) for seq in pairs): pos = BELOW
            elif any(self.layout.would_substitute('pstf', seq) for seq in pairs): pos = POST
            else: pos = BASE
            self.dynamic_positions[gid] = pos

    def _normalize(self, decoded: DecodedInput) -> Buffer:
        text = decoded.text()
        if '\0' in text: raise ShapingError('input: NUL is outside the text shaping domain')
        items, last_cluster = [], 0
        for cp, offset in zip(decoded.scalars, decoded.byte_offsets):
            # Restrict script support explicitly; a Unicode block is not a
            # language detector. ASCII punctuation/digits are useful in runs.
            if not (0x980 <= cp <= 0x9FF or cp in (0x964, 0x965, 0x200C, 0x200D, 0x25CC, 0xA0)
                    or 0x20 <= cp <= 0x40 or 0x5B <= cp <= 0x60 or 0x7B <= cp <= 0x7E):
                raise ShapingError(f'itemization: unsupported scalar U+{cp:04X} at byte {offset}')
            # Keep original text unchanged; decompose only the working sequence.
            # Bengali canonical decompositions consist of split vowels / nukta.
            cluster = last_cluster if items and (ud.category(chr(cp)).startswith('M') or cp == 0x200D) else offset
            for c in ud.normalize('NFD', chr(cp)):
                n = ord(c)
                if n not in self.cmap:
                    raise ShapingError(f'cmap: missing U+{n:04X} at original byte {offset}')
                cat, pos = properties(n)
                items.append(Item(self.cmap[n], n, cluster, cat, pos))
            last_cluster = cluster
        buf = Buffer(items)
        # Canonical ordering affects only a working combining sequence.
        for i in range(1, len(items)):
            cc = ud.combining(chr(items[i].cp)); j = i
            if not cc: continue
            while j and ud.combining(chr(items[j - 1].cp)) > cc:
                buf.merge(j - 1, j + 1)
                items[j], items[j - 1] = items[j - 1], items[j]; j -= 1
        return buf

    @staticmethod
    def _consonant(g): return g.is_category('C', 'R', 'V', 'P', 'D')

    def _initial(self, buf: Buffer, start: int, end: int):
        a = buf.items; limit = start; base = end; reph = False
        if end - start >= 3 and not a[start+2].is_category('j', 'n') and self.layout.would_substitute('rphf', (a[start].gid, a[start+1].gid)):
            limit += 2; base = start; reph = True
        seen_below = False
        for i in range(end - 1, limit - 1, -1):
            if self._consonant(a[i]):
                base = i
                if a[i].position != BELOW and (a[i].position != POST or seen_below): break
                if a[i].position == BELOW: seen_below = True
            elif i > start and a[i].is_category('j') and a[i-1].is_category('H'):
                break
        if reph and base == start and limit - base <= 2: reph = False
        for i in range(start, base): a[i].position = min(PRE_C, a[i].position)
        if base < end: a[base].position = BASE
        if reph: a[start].position = REPH
        last = START
        for i in range(start, end):
            if a[i].category in ('j', 'n', 'N', 'H'):
                a[i].position = last
                if a[i].category == 'H' and a[i].position == PRE_M:
                    for j in range(i - 1, start - 1, -1):
                        if a[j].position != PRE_M:
                            a[i].position = a[j].position; break
            elif a[i].position != SMVD: last = a[i].position
        last = base
        for i in range(base + 1, end):
            if self._consonant(a[i]):
                for j in range(last + 1, i):
                    if a[j].position < SMVD: a[j].position = a[i].position
                last = i
            elif a[i].category == 'M': last = i
        original_order = {id(g): i for i, g in enumerate(a[start:end])}
        a[start:end] = sorted(a[start:end], key=lambda g: g.position)
        base = next((i for i in range(start, end) if a[i].position == BASE), end)
        lefts = [i for i in range(start, base) if a[i].position == PRE_M]
        if len(lefts) > 1:
            # Repeated pre-base signs are diagnostic behavior, not approved
            # spelling. Preserve a sign and its following nukta as a unit.
            lo, hi = lefts[0], lefts[-1] + 1
            groups = []
            for g in a[lo:hi]:
                if g.category == 'M' or not groups: groups.append([])
                groups[-1].append(g)
            a[lo:hi] = [g for group in reversed(groups) for g in group]
        permutation = [start + original_order[id(g)] for g in a[start:end]]
        seen = set()
        for i in range(base, end):
            if i in seen: continue
            indices, j = [i], permutation[i-start]
            while j != i and j not in seen:
                indices.append(j); seen.add(j); j = permutation[j-start]
            buf.merge(max(base, min(indices)), max(indices)+1)
        for i in range(start, end):
            if a[i].position == REPH: a[i].masks.add('rphf')
            if i < base: a[i].masks.update(('half', 'blwf'))
            elif i > base: a[i].masks.update(('blwf', 'abvf', 'pstf'))
        for i in range(start+1, end):
            if a[i].is_category('n'):
                for j in range(i-1, start-1, -1):
                    a[j].masks.discard('half')
                    if self._consonant(a[j]): break

    def _final(self, buf: Buffer, start: int, end: int):
        a = buf.items
        for g in a[start:end]:
            if g.gid == self.virama and g.ligated and g.multiplied:
                g.category = 'H'; g.ligated = g.multiplied = False
        base = next((i for i in range(start, end) if a[i].position >= BASE), end)
        if start < base < end and a[base].position > BASE: base -= 1
        if base == end and start < base and a[base-1].is_category('j'): base -= 1
        if base < end:
            while start < base and a[base].is_category('N', 'H'): base -= 1
        if start + 1 < end and start < base:
            target = base - 2 if base == end else base - 1
            while True:
                while target > start and not a[target].is_category('M', 'H'): target -= 1
                if a[target].is_category('H') and a[target].position != PRE_M:
                    if target + 1 < end and a[target+1].category == 'j' and target > start:
                        target -= 1; continue
                else: target = start
                break
            if start < target and a[target].position != PRE_M:
                for i in range(target, start, -1):
                    if a[i-1].position == PRE_M:
                        obj = a.pop(i-1); a.insert(target, obj)
                        buf.merge(target, min(end, base+1)); target -= 1
            else:
                for i in range(start, base):
                    if a[i].position == PRE_M:
                        buf.merge(i, min(end, base+1)); break
        if start + 1 < end and a[start].position == REPH and a[start].ligated and not a[start].multiplied:
            target = start + 1
            while target < base and not a[target].is_category('H'): target += 1
            if target < base and a[target].is_category('H'):
                if target+1 < base and a[target+1].is_category('j', 'n'): target += 1
            else:
                target = base
                while target+1 < end and a[target+1].position not in (POST, AFTER_POST, SMVD): target += 1
                if target >= end:
                    target = end-1
                    while target > start and a[target].position == SMVD: target -= 1
            buf.merge(start, target+1); obj = a.pop(start); a.insert(target, obj)
        if a[start].position == PRE_M:
            previous = ud.category(chr(a[start-1].cp)) if start else None
            if previous is None or (not previous.startswith(('L','M')) and previous != 'Cf'):
                a[start].masks.add('init')
            else: buf.unsafe_span(start-1, start+1)

    @staticmethod
    def _runs(items):
        start = 0
        while start < len(items):
            end = start+1
            while end < len(items) and items[end].syllable == items[start].syllable: end += 1
            yield start, end
            start = end

    def shape(self, text: str, *, trace: bool = False, allow_broken: bool = False) -> ShapeResult:
        return self.shape_decoded(DecodedInput.from_text(text), trace=trace, allow_broken=allow_broken)

    def shape_decoded(self, decoded: DecodedInput, *, trace: bool = False, allow_broken: bool = False) -> ShapeResult:
        if not isinstance(decoded, DecodedInput): raise ShapingError('input: expected DecodedInput')
        if type(trace) is not bool or type(allow_broken) is not bool:
            raise ShapingError('input: trace and allow_broken must be booleans')
        original = decoded.text()
        buf = self._normalize(decoded); buf.trace_enabled = trace
        buf.snapshot('working-normalization', original_scalars=list(decoded.scalars),
                     original_byte_offsets=list(decoded.byte_offsets), unicode_data=ud.unidata_version)
        parsed = syllables(buf.items)
        kinds = {}
        # Assign identity before inserting dotted circles or applying font rules.
        for serial, (start, end, kind) in enumerate(parsed):
            if kind == 'broken' and not allow_broken:
                raise ShapingError(f'syllables: broken sequence at byte {buf.items[start].cluster}; opt in to diagnostic dotted-circle rendering')
            if kind in ('broken', 'standalone') and any(g.cp == 0x200D for g in buf.items[start:end]):
                raise ShapingError('syllables: ZWJ in dotted-circle/placeholder diagnostic clusters is not supported')
            kinds[serial] = kind
            for g in buf.items[start:end]: g.syllable = serial
            buf.unsafe_span(start, end)
        buf.snapshot('syllables', kinds=kinds)
        self.layout.apply_gsub(buf, ('locl', 'ccmp'))
        for g in buf.items:
            if g.position == BASE: g.position = self.dynamic_positions.get(g.gid, BASE)
        for start, end, kind in reversed(parsed):
            if kind == 'broken':
                if 0x25CC not in self.cmap: raise ShapingError('cmap: diagnostic dotted circle missing')
                ref = buf.items[start]
                buf.items.insert(start, Item(self.cmap[0x25CC], 0x25CC, ref.cluster, 'D', END, ref.syllable))
        for start, end in list(self._runs(buf.items)):
            if kinds[buf.items[start].syllable] not in ('other', 'symbol'): self._initial(buf, start, end)
        buf.snapshot('initial-reordering')
        for tag in BASIC:
            self.layout.apply_gsub(buf, (tag,)); buf.snapshot('basic-feature', feature=tag)
        for start, end in list(self._runs(buf.items)):
            if kinds[buf.items[start].syllable] not in ('other', 'symbol'): self._final(buf, start, end)
        buf.snapshot('final-reordering')
        self.layout.apply_gsub(buf, PRESENTATION)
        self.layout.apply_gpos(buf)
        for g in buf.items:
            if g.cp in (0x200C, 0x200D) and not g.ligated:
                g.gid = self.cmap[0x20]; g.advance = g.x_offset = g.y_offset = 0
        unsafe_clusters = {g.cluster for g in buf.items if g.unsafe}
        for g in buf.items: g.unsafe = g.cluster in unsafe_clusters
        buf.snapshot('output')
        glyphs = tuple(Glyph(g.gid, g.cluster, g.advance, 0, g.x_offset, g.y_offset,
                             int(g.unsafe)) for g in buf.items)
        if any(g.gid == 0 for g in glyphs): raise ShapingError('output: missing glyph')
        if any(a.cluster > b.cluster for a, b in zip(glyphs, glyphs[1:])):
            raise ShapingError('output: nonmonotone cluster provenance')
        return ShapeResult(original, decoded.utf8_hex.lower(), self.profile.font_sha256,
                           self.identity, glyphs, tuple(buf.events), buf.operations)
