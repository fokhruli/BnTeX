"""Emit a vocabulary-independent, fixed-profile expl3 installation.

Only installation uses Python/FontTools/pltotf. TeX execution reads ASCII rules,
font banks and the original TTF; no words or shaped runs enter this compiler.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

FONT_SHA = '32b4aeb731e3819d7a31216c885208a96e402ceeebb30fc39723b99220708fef'
PROFILE_SHA = 'f6294540099a3b6f622f2cdd9e863050390f75fd0576495d5a2316903f8cfb42'
ABI = 1
CATS = {c:i+1 for i,c in enumerate('CRVNHJZMSPDX')}
BASE, BELOW, POST, PRE_M, AFTER_SUB, AFTER_POST, SMVD, END = 4,8,11,2,9,12,14,15
CONSONANTS = set(range(0x995,0x9a9))|set(range(0x9aa,0x9b1))|{0x9b2,0x9b6,0x9b7,0x9b8,0x9b9,0x9ce,0x9dc,0x9dd,0x9df}
VOWELS = set(range(0x985,0x98d))|{0x98f,0x990,0x993,0x994,0x9e0,0x9e1}
MATRAS = {0x9be,0x9bf,0x9c0,0x9c1,0x9c2,0x9c3,0x9c4,0x9c7,0x9c8,0x9cb,0x9cc,0x9d7,0x9e2,0x9e3}
SIGNS = {0x981,0x982,0x983}
PUNCT = set(map(ord,' ,.;:!?()-[]\'"/'))|{0x964,0x965,0xa0,0x2013,0x2014,0x2018,0x2019,0x201c,0x201d}
BASIC = ('nukt','akhn','rphf','rkrf','pref','blwf','abvf','half','pstf','vatu','cjct')
PRESENTATION = ('init','pres','abvs','blws','psts','haln','calt','rclt','clig','rlig')
MASK = {tag:1<<i for i,tag in enumerate(('rphf','pref','blwf','abvf','half','pstf','init'))}
MODULES = ('bntex-auto.sty','bntex-native-styles.sty','bntex-native.sty','bntex-native-core.def','bntex-native-sub.def',
           'bntex-native-reorder.def','bntex-native-position.def','bntex-utf8.def',
           'bntex-native-integration.sty','bntex-native-memo.sty','bntex-native-reuse.sty')

def properties(cp):
    if cp in CONSONANTS:return ('R' if cp==0x9b0 else 'C'),BASE
    if cp in VOWELS:return 'V',BASE
    if cp==0x9bc:return 'N',END
    if cp==0x9cd:return 'H',BELOW
    if cp==0x200d:return 'J',END
    if cp==0x200c:return 'Z',END
    if cp in SIGNS:return 'S',SMVD
    if cp in MATRAS:return 'M',PRE_M if cp in (0x9bf,0x9c7,0x9c8) else AFTER_SUB if cp in (0x9c1,0x9c2,0x9c3,0x9c4,0x9e2,0x9e3) else AFTER_POST
    if 0x9e6<=cp<=0x9ef or 0x30<=cp<=0x39 or cp==0xa0:return 'P',BASE
    if cp==0x25cc:return 'D',BASE
    if cp in PUNCT:return 'X',END
    return None


def grammar_dfa():
    """Compile the issue-5 Bengali grammar, not input strings, to a finite DFA.

    Thompson construction; grammar adapted from HarfBuzz's published Indic model.
    See THIRD-PARTY-NOTICES.md and docs/NATIVE-TEX.md for attribution and domain.
    """
    eps=[];edges=[];accept={}
    def state():eps.append(set());edges.append([]);return len(eps)-1
    root=state()
    def atom(chars):
        a,b=state(),state();edges[a].append((set(chars),b));return a,b
    def seq(*parts):
        a,b=parts[0]
        for c,d in parts[1:]:eps[b].add(c);b=d
        return a,b
    def alt(*parts):
        a,b=state(),state()
        for c,d in parts:eps[a].add(c);eps[d].add(b)
        return a,b
    def opt(t):
        a,b=state(),state();eps[a].update((t[0],b));eps[t[1]].add(b);return a,b
    def star(t):
        a,b=opt(t);eps[t[1]].add(t[0]);return a,b
    def cn():return seq(atom('CR'),opt(atom('J')),opt(seq(atom('N'),opt(atom('N')))))
    def halant():return seq(opt(atom('JZ')),atom('H'),opt(seq(atom('J'),opt(atom('N')))))
    def matra():return seq(star(atom('JZ')),atom('M'),opt(atom('N')),opt(atom('H')))
    def tail():return opt(seq(opt(atom('JZ')),atom('S'),opt(atom('S')),opt(atom('Z'))))
    def complex_tail():return seq(star(seq(halant(),cn())),alt(halant(),seq(atom('H'),atom('Z')),star(matra())),tail())
    def reph():return seq(atom('R'),atom('H'))
    patterns=[seq(cn(),complex_tail()),seq(opt(reph()),atom('V'),opt(atom('N')),alt(atom('J'),complex_tail())),
              seq(alt(atom('P'),seq(opt(reph()),atom('D'))),opt(atom('N')),complex_tail()),
              seq(opt(reph()),opt(seq(atom('N'),opt(atom('N')))),complex_tail()),atom('XCRVNHJZMSPD')]
    for i,(a,b) in enumerate(patterns,1):eps[root].add(a);accept[b]=i
    def closure(initial):
        found=set(initial);todo=list(initial)
        while todo:
            for s in eps[todo.pop()]:
                if s not in found:found.add(s);todo.append(s)
        return frozenset(found)
    states=[closure({root})];numbers={states[0]:1};trans={};accepted={}
    for subset in states:
        ident=numbers[subset];kinds=[accept[s] for s in subset if s in accept]
        accepted[ident]=min(kinds) if kinds else 0
        for cat,cid in CATS.items():
            target=closure({d for s in subset for chars,d in edges[s] if cat in chars})
            if not target:continue
            if target not in numbers:numbers[target]=len(states)+1;states.append(target)
            trans[ident,cid]=numbers[target]
        if len(states)>2048:raise ValueError('Grammar DFA exceeds installation budget')
    return trans,accepted


def entry_glyphs(subtable: dict) -> tuple[int, ...]:
    """Conservative first-input coverage, not an example-text index.

    Keep all pair-class coverage (including zero-valued class-zero rules) and
    all contextual input coverage (including zero-action blocking rules).
    Nested lookup references and original subtable/rule order stay unchanged.
    """
    kind = subtable['kind']
    if kind in ('single', 'multiple', 'pair-glyph'):
        glyphs = (row[0] for row in subtable['entries'])
    elif kind == 'ligature':
        glyphs = (pattern[0] for pattern, _ in subtable['entries'])
    elif kind == 'chain':
        glyphs = subtable['inputs'][0]
    elif kind == 'pair-class':
        glyphs = subtable['coverage']
    elif kind in ('mark-base', 'mark-mark'):
        glyphs = (row[0] for row in subtable['marks'])
    else:
        raise ValueError(f'No first-input dispatch for {kind!r}')
    return tuple(sorted(set(glyphs)))


def mark_pair_declaration(rule: int, lookup: int, flags: int, glyphs) -> str | None:
    """Compile ONLY two-input IgnoreMarks ligatures; never a document word.

    The runtime dispatch additionally requires manual join-control mode. Under
    this guard the sole skip predicate is the font's static IgnoreMarks table.
    The generic matcher remains authoritative for every other lookup form.
    """
    if flags != 8 or len(glyphs) != 2:
        return None
    numbers = (rule, lookup, *glyphs)
    if any(type(n) is not int or not 0 <= n <= 65535 for n in numbers):
        raise ValueError('Invalid generated matcher index')
    a, b = glyphs
    return (rf'\cs_gset_protected:cpn {{__bnp_r_{rule}_mark_pair}}#1#2#3'
            rf'{{\__bn_match_mark_pair:nnnnnn{{#1}}{{{a}}}{{{b}}}{{{lookup}}}{{#2}}{{#3}}}}')


def emit_tables(p:dict)->bytes:
    """Internal ASCII table serializer, called only after an exact profile hash check."""
    lines=['% BnTeX native profile ABI 1. Installation data; no vocabulary.',r'\ExplSyntaxOn']
    def put(key,value):
        if not re.fullmatch(r'[a-zA-Z0-9_]+',key):raise ValueError('Unsafe internal table key')
        if isinstance(value,(list,tuple)):value=','.join(map(str,value))
        value=str(value)
        if not re.fullmatch(r'[-0-9a-zA-Z_,.]*',value):raise ValueError('Unsafe table value')
        lines.append(r'\cs_gset:cpn {__bnp_'+key+'}{'+value+'}')
    put('abi',ABI);put('font',FONT_SHA);put('profile',PROFILE_SHA);put('upem',p['upem'])
    for cp,g in p['cmap']:
        if properties(cp):
            cat,pos=properties(cp);put(f'cp_{cp}_g',g);put(f'cp_{cp}_c',CATS[cat]);put(f'cp_{cp}_p',pos)
    for gid,adv in enumerate(p['advances']):
        put(f'm_{gid}_a',adv);put(f'm_{gid}_class',p['glyph_classes'][gid])
        for field,v in zip(('x0','y0','x1','y1'),p['bounds'][gid] or (0,0,0,0)):put(f'm_{gid}_{field}',v)
    trans,accepted=grammar_dfa()
    for (s,c),t in trans.items():put(f'dfa_{s}_{c}',t)
    for s,k in accepted.items():put(f'accept_{s}',k)
    coverage_ids={};pattern_ids={}
    def coverage(gs):
        gs=tuple(gs)
        if gs not in coverage_ids:
            cid=len(coverage_ids)+1;coverage_ids[gs]=cid
            for g in sorted(set(gs)):put(f'cov_{cid}_{g}',1)
        return coverage_ids[gs]
    def pattern(covs):
        key=tuple(coverage(c) for c in covs)
        if key not in pattern_ids:
            pid=len(pattern_ids)+1;pattern_ids[key]=pid;put(f'pat_{pid}',key)
        return pattern_ids[key]
    tid=0;rid=0
    for table,letter in (('gsub','s'),('gpos','p')):
        for lookup in p[table]:
            lid=lookup['index'];tids=[]; candidates={}
            direct_pair = (letter == 's' and lookup['flags'] == 0
                           and all(st['kind'] == 'ligature' for st in lookup['subtables']))
            if direct_pair:
                put(f's_{lid}_pair_mode', 1)
                for a, b in sorted({tuple(pattern[:2]) for st in lookup['subtables']
                                    for pattern, _ in st['entries']}):
                    put(f's_{lid}_pair_{a}_{b}', 1)
            for g,c in enumerate(p['glyph_classes']):
                f=lookup['flags'];skip=(c==1 and f&2) or (c==2 and f&4)
                if c==3:
                    skip=bool(f&8) or (g not in p['mark_filter_sets'][lookup['mark_filter_set']] if f&16 else bool(f>>8 and p['mark_attach_classes'][g]!=f>>8))
                if skip:put(f'ignore_{letter}_{lid}_{g}',1)
            for st in lookup['subtables']:
                tid+=1;tids.append(tid);pre=f't_{tid}_';kind=st['kind']
                for glyph in entry_glyphs(st):
                    candidates.setdefault(glyph, []).append(tid)
                put(pre+'type',{'single':1,'multiple':2,'ligature':4,'chain':6,'pair-glyph':12,'pair-class':13,'mark-base':14,'mark-mark':16}[kind])
                if kind in ('single','multiple'):
                    for a,b in st['entries']:put(pre+f'map_{a}',b)
                elif kind=='ligature':
                    rules=[]; by_first={}; by_pair={}
                    for gs,g in st['entries']:
                        rid+=1;rules.append(rid);put(f'r_{rid}_first',gs[0]);put(f'r_{rid}_out',g);put(f'r_{rid}_pat',pattern([(a,) for a in gs]))
                        by_first.setdefault(gs[0], []).append(rid)
                        by_pair.setdefault(tuple(gs[:2]), []).append(rid)
                    put(pre+'rules',rules)
                    for glyph, rule_ids in sorted(by_first.items()):
                        put(pre+f'rules_at_{glyph}', rule_ids)
                    if direct_pair:
                        for (a, b), rule_ids in sorted(by_pair.items()):
                            put(pre+f'rules_pair_{a}_{b}', rule_ids)
                elif kind=='chain':
                    for key in ('inputs','backtrack','lookahead'):put(pre+key,pattern(st[key]))
                    put(pre+'actions',len(st['actions']))
                    for i,(slot,ref) in enumerate(st['actions']):put(pre+f'act_{i}_slot',slot);put(pre+f'act_{i}_ref',ref)
                elif kind in ('pair-glyph','pair-class'):
                    put(pre+'second',int(st['value2_present']))
                    def pair(key,a,b):
                        for owner,v in enumerate((a,b)):
                            for field,name in (('dx','x_placement'),('dy','y_placement'),('ax','x_advance'),('ay','y_advance')):put(pre+f'{key}_{owner}_{field}',v[name])
                    if kind=='pair-glyph':
                        for a,b,v,w in st['entries']:put(pre+f'pair_{a}_{b}',1);pair(f'pair_{a}_{b}',v,w)
                    else:
                        put(pre+'coverage',coverage(st['coverage']))
                        for a,b in st['class1']:put(pre+f'c1_{a}',b)
                        for a,b in st['class2']:put(pre+f'c2_{a}',b)
                        for a,row in enumerate(st['matrix']):
                            for b,(v,w) in enumerate(row):pair(f'pair_{a}_{b}',v,w)
                else:
                    for g,c,a in st['marks']:
                        put(pre+f'mark_{g}',1);put(pre+f'mark_{g}_c',c);put(pre+f'mark_{g}_x',a['x']);put(pre+f'mark_{g}_y',a['y'])
                    for g,anchors in st['bases']:
                        for c,a in enumerate(anchors):
                            if a is not None:put(pre+f'base_{g}_{c}',1);put(pre+f'base_{g}_{c}_x',a['x']);put(pre+f'base_{g}_{c}_y',a['y'])
            put(f'{letter}_{lid}_subs',tids)
            for glyph, selected in sorted(candidates.items()):
                put(f'{letter}_{lid}_at_{glyph}', selected)
    sf={f['tag']:f['lookups'] for f in p['gsub_features']};gs={l['index']:l for l in p['gsub']}
    def would(tag,parts):return any(st['kind']=='ligature' and any(tuple(a)==tuple(parts) for a,_ in st['entries']) for i in sf.get(tag,()) for st in gs[i]['subtables'])
    h=dict(p['cmap'])[0x9cd]
    for gid in range(p['glyph_count']):
        pairs=((h,gid),(gid,h))
        pos=BELOW if any(would(f,x) for f in ('blwf','vatu') for x in pairs) else POST if any(would(f,x) for f in ('pstf','pref') for x in pairs) else BASE
        put(f'dyn_{gid}',pos)
    for i in sf.get('rphf',()):
        for st in gs[i]['subtables']:
            if st['kind']=='ligature':
                for parts,_ in st['entries']:
                    if len(parts)==2:put(f'reph_{parts[0]}_{parts[1]}',1)
    masks=set(MASK.values())
    for stage,tags in [('initial',('locl','ccmp'))]+[(f,(f,)) for f in BASIC]+[('presentation',PRESENTATION)]:
        roots={}
        for tag in tags:
            for i in sf.get(tag,()):roots.setdefault(i,set()).add(tag)
        calls=[]
        for i,features in sorted(roots.items()):
            mask=sum(MASK[f] for f in features) if features <= MASK.keys() else 0;masks.add(mask)
            manual=int(not features&{'locl','ccmp','calt','rclt'});per=int(not features&{'calt','rclt'})
            calls.append(r'\__bn_gsub_run:nnnn{'+f'{i}'+'}{'+f'{mask}'+'}{'+f'{manual}'+'}{'+f'{per}'+'}')
        lines.append(r'\cs_gset:cpn {__bnp_stage_'+stage+'}{'+''.join(calls)+'}')
    for mask in masks:
        for n in range(128):put(f'mask_{mask}_{n}',int(mask==0 or bool(mask&n)))
    put('dispatch_abi', 1)
    put('gpos_roots',sorted({i for f in p['gpos_features'] for i in f['lookups']}))
    # Monotone per-run lookup activation. Mark every lookup that could start
    # at an observed glyph, including zero-action blockers. No vocabulary input.
    put('activity_abi', 1)
    for g in range(p['glyph_count']):
        actions = []
        for table, letter in [('gsub', 's'), ('gpos', 'p')]:
            for lookup in p[table]:
                if lookup['index'] >= 128:
                    raise ValueError('lookup exceeds native activity table bounds')
                if any(g in entry_glyphs(sub) for sub in lookup['subtables']):
                    actions.append(r'\cs_gset_eq:cN{__bn_active_' + letter + '_' +
                        str(lookup['index']) + r'}\g__bn_activity_stamp_tl')
        lines.append(r'\cs_gset:cpn {__bnp_activate_' + str(g) + '}{' + ''.join(actions) + '}')
    lines += [r'\ExplSyntaxOff',r'\endinput']
    return ('\n'.join(lines)+'\n').encode('ascii')



def emit_matchers(p: dict) -> bytes:
    """Emit separate font-derived code without changing the original rule tables.

    Rule IDs use exactly the ligature traversal in emit_tables. The input is an
    already fingerprint-verified profile, not document text or a word cache.
    """
    lines = ['% Fixed-profile IgnoreMarks pair matchers; no document vocabulary.',
             r'\ExplSyntaxOn',
             r'\cs_if_exist:NF\__bn_match_mark_pair:nnnnnn{\__bn_fail:n{matching~pair~runtime~required}}']
    rule = 0
    for lookup in p['gsub']:
        for subtable in lookup['subtables']:
            if subtable['kind'] != 'ligature':
                continue
            for glyphs, _ in subtable['entries']:
                rule += 1
                declaration = mark_pair_declaration(rule, lookup['index'], lookup['flags'], glyphs)
                if declaration is not None:
                    lines.append(declaration)
    lines += [r'\ExplSyntaxOff', r'\endinput']
    return ('\n'.join(lines)+'\n').encode('ascii')


ZWSP = chr(0x200B)


def _usable(cp: int) -> bool:
    """Controls, surrogates and private-use code points never become copied text."""
    return cp >= 0x20 and not 0x7F <= cp <= 0x9F and not 0xD800 <= cp <= 0xF8FF


def glyph_text(p: dict, names: list[str] | None = None) -> dict[int, str]:
    """Map each reachable glyph to the Unicode text it stands for.

    The pinned font names its glyphs by Adobe Glyph List rules (uni09CD09AF is
    HASANT+YA, uni09BF09B009CD is I-KAR with a merged reph), so names decide
    first. Several GSUB lookups only serve drawing (swapping a consumed glyph for
    the empty uni200B, or borrowing a glyph inside a context), so following them
    would attach the wrong text; they only fill glyphs whose names say nothing.
    Two kinds of glyph stand for nothing and become an invisible U+200B: the
    space glyph, which BnTeX only draws (zero-width) for a hidden ZWJ/ZWNJ since
    real spaces are TeX glue, and suffixed stacking helpers named after Vedic
    signs (uni1CF5.stack). Pre-base matras map to themselves, so viewers that
    read glyphs in drawing order see them before their consonant; the per-word
    /ActualText keeps logical order for viewers that honour it.
    """
    text: dict[int, str] = {}
    if names is not None:
        from fontTools.agl import toUnicode
        for glyph, name in enumerate(names):
            value = toUnicode(name)
            if not value or not all(_usable(ord(c)) for c in value):
                continue
            helper = name == 'space' or ('.' in name and any(0x1CD0 <= ord(c) <= 0x1CFF for c in value))
            text[glyph] = ZWSP if helper else value
    for cp, glyph in sorted(p['cmap']):
        if _usable(cp):
            text.setdefault(glyph, chr(cp))
    changed = True
    while changed:
        changed = False
        for lookup in p['gsub']:
            for subtable in lookup['subtables']:
                kind = subtable['kind']
                if kind == 'single':
                    pairs = [(a, b) for a, b in subtable['entries']]
                elif kind == 'multiple':
                    pairs = [(a, seq[0]) for a, seq in subtable['entries'] if len(seq) == 1]
                elif kind == 'ligature':
                    for glyphs, lig in subtable['entries']:
                        if lig not in text and all(g in text for g in glyphs):
                            text[lig] = ''.join(text[g] for g in glyphs); changed = True
                    continue
                else:
                    continue
                for a, b in pairs:
                    if b not in text and a in text:
                        text[b] = text[a]; changed = True
    return text


def emit_tounicode(p: dict, names: list[str]) -> bytes:
    """pdfTeX glyph-name table so PDF viewers can copy and search Bengali.

    Bank encodings name glyphs /index<gid>, so pdfTeX's ToUnicode CMaps are empty
    without this table. Regular and Bold share glyph order and substitutions (the
    authoring exporter proves it), so one global table serves both faces.
    """
    lines = ['% Glyph-to-Unicode names for PDF text extraction; no document vocabulary.',
             '% pdfTeX writes these into each bank font\'s /ToUnicode CMap.',
             r'\ifnum\pdfgentounicode=0 \pdfgentounicode=1 \fi']
    if len(names) != p['glyph_count']:
        raise ValueError('Glyph names do not match the profile')
    for glyph, value in sorted(glyph_text(p, names).items()):
        if any(ord(c) > 0xFFFF for c in value):
            continue
        codes = ' '.join(f'{ord(c):04X}' for c in value)
        lines.append(rf'\pdfglyphtounicode{{index{glyph}}}{{{codes}}}')
    lines.append(r'\endinput')
    return ('\n'.join(lines)+'\n').encode('ascii')


def export(profile_path:Path,font_path:Path,out:Path)->dict:
    if profile_path.stat().st_size>8*1024*1024:raise ValueError('Profile too large')
    raw=profile_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PROFILE_SHA:raise ValueError('Unsupported compiled profile fingerprint')
    if font_path.stat().st_size>64*1024*1024 or hashlib.sha256(font_path.read_bytes()).hexdigest()!=FONT_SHA:raise ValueError('Wrong font binary')
    if out.exists() or out.is_symlink():raise ValueError('Output must not exist')
    if any(p.is_symlink() for p in (out,*out.parents)):raise ValueError('Symlink output path rejected')
    p=json.loads(raw);tables=emit_tables(p);matchers=emit_matchers(p)
    from .build import inspect_font,_write_banks
    from importlib.resources import files
    source_root=Path(__file__).resolve().parents[2]/'tex'/'latex'/'bntex'
    resources={}
    for name in MODULES:
        local=source_root/name
        resources[name]=local.read_bytes() if local.is_file() else files('bntex').joinpath('data',name).read_bytes()
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bntex-native-',dir=out.parent) as temp:
        stage=Path(temp)/'installation';stage.mkdir()
        meta=inspect_font(font_path)
        mapping,maplines=_write_banks(stage,font_path,meta,set(range(p['glyph_count'])))
        if hashlib.sha256((stage/meta['prepared_font_filename']).read_bytes()).hexdigest()!=FONT_SHA:raise ValueError('Font changed during installation')
        for name,body in resources.items():(stage/name).write_bytes(body)
        (stage/'bntex-native-tables.def').write_bytes(tables)
        (stage/'bntex-native-matchers.def').write_bytes(matchers)
        from fontTools.ttLib import TTFont
        with TTFont(font_path) as font:
            (stage/'bntex-native-tounicode.def').write_bytes(emit_tounicode(p,font.getGlyphOrder()))
        checks=[]
        for path in sorted(stage.iterdir()):
            if path.suffix=='.pl':path.unlink();continue
            checks.append(r'\BnTeXNativeCheckFile{'+path.name+'}{'+hashlib.md5(path.read_bytes()).hexdigest().upper()+'}')
        prefix='bnf'+FONT_SHA[:16]
        loader=['% Trusted installation manifest; MD5 detects accidental drift, not authentication.',*checks,*maplines,
                r'\ExplSyntaxOn',r'\cs_gset:Npn \__bn_font_prefix: {'+prefix+'}',r'\ExplSyntaxOff',
                r'\input{bntex-native-tables.def}',r'\input{bntex-native-matchers.def}',r'\input{bntex-native-tounicode.def}',
                r'\BnTeXNativeProfileReady{1}{'+FONT_SHA+'}{'+PROFILE_SHA+'}',r'\endinput']
        (stage/'bntex-native-profile.tex').write_text('\n'.join(loader)+'\n',encoding='ascii',newline='\n')
        manifest={'abi':ABI,'font_sha256':FONT_SHA,'profile_sha256':PROFILE_SHA,'tables_sha256':hashlib.sha256(tables).hexdigest(),
          'table_bytes':len(tables),'matchers_sha256':hashlib.sha256(matchers).hexdigest(),'matcher_bytes':len(matchers),'glyph_count':p['glyph_count'],'vocabulary':None,'files':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(stage.iterdir())}}
        (stage/'native-installation.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',newline='\n')
        stage.rename(out)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True);parser.add_argument('--font',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args(argv)
    try:print(json.dumps(export(a.profile,a.font,a.out),indent=2));return 0
    except (OSError,ValueError,RuntimeError) as e:print(f'bntex native export: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
