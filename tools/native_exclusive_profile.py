#!/usr/bin/env python3
"""Diagnostic, nesting-aware TeX phase timing; never a production shaper patch.

The exclusive totals partition the INSTRUMENTED body, not uninstrumented CPU time.
Plain/instrumented subprocess times and output equality are reported separately.
Python only launches pdfTeX and validates its output after it has exited.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import native_performance as perf
import native_decode_benchmark as fixtures

PHASES = [
 ('unattributed', '', 0), ('decode_collect', 'bntex_utfviii_decode:nTF', 3),
 ('execute_other','__bn_execute:',0), ('normalize','__bn_normalize:',0),
 ('syllables','__bn_syllables:',0), ('initial_reorder','__bn_initial:',0),
 ('substitution','__bn_gsub_run:nnnn',4), ('final_reorder','__bn_final:',0),
 ('position','__bn_position:',0), ('render','__bn_render:',0),
 ('allocate','__bn_allocate:',0), ('clone','__bn_clone:n',1),
 ('match','__bn_match:nnnnnnnn',8)]


def instrumentation(detail=False):
    code = r'''\ExplSyntaxOn
\intarray_new:Nn\g__bne_self_intarray{13}
\intarray_new:Nn\g__bne_inclusive_intarray{13}
\intarray_new:Nn\g__bne_calls_intarray{13}
\intarray_new:Nn\g__bne_tags_intarray{64}
\intarray_new:Nn\g__bne_starts_intarray{64}
\int_new:N\g__bne_depth_int
\int_new:N\g__bne_last_int
\int_new:N\g__bne_now_int
\int_new:N\g__bne_tag_int
\cs_new:Npn\__bne_clock:{\pdfelapsedtime}
\cs_new_protected:Npn\__bne_charge:
 {\int_gset:Nn\g__bne_now_int{\__bne_clock:}
  \int_compare:nNnT{\g__bne_now_int}<{\g__bne_last_int}{\errmessage{profiler~clock~wrapped}}
  \int_gset:Nn\g__bne_tag_int{\intarray_item:Nn\g__bne_tags_intarray{\g__bne_depth_int}}
  \intarray_gset:Nnn\g__bne_self_intarray{\g__bne_tag_int+1}
   {\intarray_item:Nn\g__bne_self_intarray{\g__bne_tag_int+1}+\g__bne_now_int-\g__bne_last_int}}
\cs_new_protected:Npn\__bne_enter:n#1
 {\int_compare:nNnT{#1}<{1}{\errmessage{profiler~tag~range}}
  \int_compare:nNnT{#1}>{12}{\errmessage{profiler~tag~range}}
  \int_compare:nNnT{\g__bne_depth_int}<{1}{\errmessage{profiler~not~running}}
  \int_compare:nNnT{\g__bne_depth_int}>{63}{\errmessage{profiler~stack~limit}}
  \__bne_charge:\int_gincr:N\g__bne_depth_int
  \intarray_gset:Nnn\g__bne_tags_intarray{\g__bne_depth_int}{#1}
  \intarray_gset:Nnn\g__bne_starts_intarray{\g__bne_depth_int}{\g__bne_now_int}
  \intarray_gset:Nnn\g__bne_calls_intarray{#1+1}{\intarray_item:Nn\g__bne_calls_intarray{#1+1}+1}
  \int_gset_eq:NN\g__bne_last_int\g__bne_now_int}
\cs_new_protected:Npn\__bne_exit:
 {\int_compare:nNnT{\g__bne_depth_int}<{2}{\errmessage{profiler~stack~underflow}}
  \__bne_charge:
  \intarray_gset:Nnn\g__bne_inclusive_intarray{\g__bne_tag_int+1}
   {\intarray_item:Nn\g__bne_inclusive_intarray{\g__bne_tag_int+1}+\g__bne_now_int-\intarray_item:Nn\g__bne_starts_intarray{\g__bne_depth_int}}
  \int_gdecr:N\g__bne_depth_int\int_gset_eq:NN\g__bne_last_int\g__bne_now_int}
\cs_new_protected:Npn\__bne_start:
 {\int_compare:nNnF{\g__bne_depth_int}={0}{\errmessage{profiler~already~running}}
  \int_step_inline:nn{13}{\intarray_gset:Nnn\g__bne_self_intarray{##1}{0}\intarray_gset:Nnn\g__bne_inclusive_intarray{##1}{0}\intarray_gset:Nnn\g__bne_calls_intarray{##1}{0}}
  \int_gset:Nn\g__bne_depth_int{1}\intarray_gset:Nnn\g__bne_tags_intarray{1}{0}
  \int_gset:Nn\g__bne_last_int{\__bne_clock:}\intarray_gset:Nnn\g__bne_starts_intarray{1}{\g__bne_last_int}}
\cs_new_protected:Npn\__bne_stop:
 {\int_compare:nNnF{\g__bne_depth_int}={1}{\errmessage{profiler~unbalanced~stack}}
  \__bne_charge:\intarray_gset:Nnn\g__bne_inclusive_intarray{1}{\g__bne_now_int-\intarray_item:Nn\g__bne_starts_intarray{1}}
  \intarray_gset:Nnn\g__bne_calls_intarray{1}{1}\int_gzero:N\g__bne_depth_int}
'''
    for i, (_, name, arity) in enumerate(PHASES):
        if i == 0 or (i >= 10 and not detail):
            continue
        code += rf'\cs_new_eq:cN{{__bne_saved_{i}:}}\{name}'+'\n'
        params=''.join(f'#{j}' for j in range(1,arity+1))
        args=''.join('{#'+str(j)+'}' for j in range(1,arity+1))
        if i == 1:
            body = rf'\__bne_enter:n{{{i}}}\use:c{{__bne_saved_{i}:}}{{#1}}{{\__bne_exit:#2}}{{\__bne_exit:#3}}'
        else:
            body = rf'\__bne_enter:n{{{i}}}\use:c{{__bne_saved_{i}:}}'+args+r'\__bne_exit:'
        code += rf'\cs_set_protected:Npn\{name}'+params+'{'+body+'}\n'
    if detail:
        # Same phase as the generic matcher, including recursive observer state.
        # Older installations simply lack this explicitly guarded entry point.
        code += r"""\cs_if_exist:NT\__bn_match_mark_pair:nnnnnn
 {\cs_new_eq:NN\__bne_saved_mark_pair:nnnnnn\__bn_match_mark_pair:nnnnnn
  \cs_set_protected:Npn\__bn_match_mark_pair:nnnnnn#1#2#3#4#5#6
   {\__bne_enter:n{12}\__bne_saved_mark_pair:nnnnnn{#1}{#2}{#3}{#4}{#5}{#6}\__bne_exit:}}
"""
    return code+r'\ExplSyntaxOff'+'\n'


def markers():
    start=r'\ExplSyntaxOn\__bne_start:\ExplSyntaxOff'
    stop=r'\ExplSyntaxOn\__bne_stop:'
    for i,(name,_,_) in enumerate(PHASES):
        stop += (r'\iow_term:x{BNTEX-PROFILE|'+name+
                 rf'|\intarray_item:Nn\g__bne_calls_intarray{{{i+1}}}'+
                 rf'|\intarray_item:Nn\g__bne_self_intarray{{{i+1}}}'+
                 rf'|\intarray_item:Nn\g__bne_inclusive_intarray{{{i+1}}}'+'}')
    return start,stop+r'\ExplSyntaxOff'


def instrument_source(source,detail=False):
    if source.count(r'\begin{document}')!=1 or source.count(r'\end{document}')!=1:
        raise ValueError('expected one fixed-fixture document')
    start,stop=markers()
    return source.replace(r'\begin{document}', instrumentation(detail)+r'\begin{document}'+start).replace(r'\end{document}',stop+r'\end{document}')


def parse(log):
    rows=re.findall(r'BNTEX-PROFILE\|([a-z_]+)\|(\d+)\|(\d+)\|(\d+)',log)
    names=[p[0] for p in PHASES]
    if [r[0] for r in rows]!=names:
        raise ValueError('missing, duplicate or out-of-order profiler records')
    data={n:dict(calls=int(c),exclusive_ticks=int(s),inclusive_ticks=int(t)) for n,c,s,t in rows}
    total=data['unattributed']['inclusive_ticks']
    if total<=0 or sum(r['exclusive_ticks'] for r in data.values())!=total:
        raise ValueError('exclusive times do not partition instrumented block')
    for n,r in data.items():
        if r['exclusive_ticks']>r['inclusive_ticks']:
            raise ValueError('exclusive time exceeds inclusive time')
        r['exclusive_fraction']=r['exclusive_ticks']/total
    return {'instrumented_body_ticks':total,'phases':data}


def drawing_identity(path):
    """Compare operators plus complete font resources, ignoring PDF object names.

    expl3 integer arrays can change internal font IDs when instrumentation is
    loaded. Do not mask font data, coordinates, glyph strings or ActualText.
    """
    from pypdf import PdfReader
    from pypdf.generic import (ContentStream, DictionaryObject, ArrayObject,
                              StreamObject, ByteStringObject, TextStringObject)
    def value(obj, depth=0):
        if depth > 32:
            raise ValueError('unexpected resource recursion')
        obj = obj.get_object() if hasattr(obj, 'get_object') else obj
        if isinstance(obj, StreamObject):
            return {'dictionary':{str(k):value(v,depth+1) for k,v in obj.items()
                                  if k not in ('/Length','/Filter','/DecodeParms')},
                    'decoded_stream_sha256':perf.sha(obj.get_data())}
        if isinstance(obj, DictionaryObject):
            return {str(k):value(v,depth+1) for k,v in obj.items()}
        if isinstance(obj, (ArrayObject,list,tuple)):
            return [value(v,depth+1) for v in obj]
        if isinstance(obj, bytes):
            return {'bytes':obj.hex()}
        if isinstance(obj, TextStringObject):
            return {'text':str(obj)}
        if obj is None or isinstance(obj,(bool,int,float,str)):
            return obj
        return str(obj)
    reader=PdfReader(path); pages=[]
    for page in reader.pages:
        resources=page['/Resources']
        if set(resources)-{'/Font','/ProcSet'} or page.get('/Annots'):
            raise ValueError('drawing identity supports only the fixed text fixtures')
        fonts=resources.get('/Font',{})
        fonts=fonts.get_object() if hasattr(fonts,'get_object') else fonts
        identities={str(k):perf.sha(json.dumps(value(v),sort_keys=True).encode()) for k,v in fonts.items()}
        operations=[]
        for operands,operator in ContentStream(page.get_contents(),reader).operations:
            row=value(operands)
            if operator==b'Tf':
                row[0]=identities[str(operands[0])]
            operations.append([operator.decode('ascii'),row])
        pages.append({'box':value(page.mediabox),'crop':value(page.cropbox),'rotate':int(page.get('/Rotate',0)),'operations':operations,
                      'fonts':sorted(identities.values())})
    return perf.sha(json.dumps(pages,sort_keys=True,ensure_ascii=True).encode())


def run(installation,out,*,kind='prose',repetitions=3,detail=False,timeout=60,memo=False):
    if type(repetitions) is not int or not 1<=repetitions<=5 or type(memo) is not bool:
        raise ValueError('repetitions must be 1..5 and memo must be Boolean')
    if out.exists() or any(p.is_symlink() for p in (out,*out.parents)):
        raise ValueError('output must be new and not symlinked')
    assets,identity=perf.installation(installation)
    src,meta,words=fixtures.make_source(kind,1,memo)
    versions={'plain':src,'profiled':instrument_source(src,detail)}
    out.mkdir(parents=True)
    report={'schema':1,'installation':identity,'fixture':meta,'detail':detail,
            'note':'Exclusive times partition the instrumented body, including observer overhead; not uninstrumented CPU shares.',
            'samples':[]}
    for rep in range(repetitions):
        for name in (('plain','profiled') if rep%2==0 else ('profiled','plain')):
            root=out/f'{rep}-{name}';root.mkdir()
            for n,raw in assets.items():(root/n).write_bytes(raw)
            (root/'main.tex').write_text(versions[name])
            result=perf.compile_run(root,assets,words,1,timeout)
            if result['status']=='compiled':
                result['drawing_sha256']=drawing_identity(root/'main.pdf')
            sample={'repetition':rep+1,'mode':name,'source_sha256':perf.sha(versions[name].encode()),'result':result}
            if result['status']=='compiled' and name=='profiled':
                try:
                    sample['profile']=parse((root/'main.log').read_text(errors='replace'))
                except ValueError as exc:
                    sample['profile_error']=str(exc)
            report['samples'].append(sample)
            (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    report['all_drawings_equal']=len({s['result'].get('drawing_sha256') for s in report['samples']})==1 and all(s['result']['status']=='compiled' and 'profile_error' not in s for s in report['samples'])
    report['all_pdfs_byte_identical']=len({s['result'].get('pdf_sha256') for s in report['samples']})==1 and all(s['result']['status']=='compiled' for s in report['samples'])
    report['summary']={}
    for name in versions:
        times=[s['result']['runs'][0]['wall_seconds'] for s in report['samples'] if s['mode']==name and s['result']['status']=='compiled']
        report['summary'][name]={'successful_samples':len(times),'median_seconds':statistics.median(times) if times else None,
                               'min_seconds':min(times) if times else None,'max_seconds':max(times) if times else None}
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not report['all_drawings_equal']:
        raise ValueError('compilation/drawing equality failed; see retained evidence')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installation',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--kind',choices=('distinct','repeated','digits-free','prose'),default='prose')
    p.add_argument('--repetitions',type=int,default=3);p.add_argument('--detail',action='store_true')
    p.add_argument('--memo',action='store_true',help='Enable existing process-local reuse; report separately from first-use timing')
    args=p.parse_args()
    try:
        result=run(args.installation,args.out,kind=args.kind,repetitions=args.repetitions,detail=args.detail,memo=args.memo)
        print(json.dumps(result['summary'],indent=2))
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)

if __name__=='__main__':main()
