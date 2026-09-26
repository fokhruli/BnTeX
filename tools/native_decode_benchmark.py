#!/usr/bin/env python3
"""Paired fresh-process benchmark for decode-once; trusted installations only.

Python coordinates measurements outside pdfTeX. Font preparation, extraction and
validation are excluded from the measured compile interval. No runtime helper is
invoked. Run this serially, not concurrently with the regression suite.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

import native_performance as perf

# Original, authored typography fixture. Not a mined corpus or approved benchmark.
PROSE = (
    'আমাদের গবেষণার উদ্দেশ্য বাংলা ভাষায় সহজে নথি তৈরি করা। '
    'প্রতিটি শব্দের মূল বানান ও অক্ষরের বিন্যাস সংরক্ষণ করতে হবে। '
    'শিক্ষার্থীরা শ্রেণিকক্ষে বিভিন্ন প্রশ্ন আলোচনা করে এবং পরীক্ষার ফলাফল লিখে রাখে। '
    'নতুন প্রযুক্তি ব্যবহারের আগে তার নির্ভরযোগ্যতা যাচাই করা প্রয়োজন। '
    'ক্ষুদ্র পরিবর্তনের পরেও যুক্তাক্ষর ও স্বরচিহ্নের অবস্থান ঠিক আছে কি না দেখা উচিত। '
    'স্বাস্থ্যসেবা কৃষি শিক্ষা এবং যোগাযোগের ক্ষেত্রে তথ্যের সঠিক উপস্থাপন গুরুত্বপূর্ণ। '
    'পৃথক শব্দের পাশাপাশি সম্পূর্ণ বাক্য অনুচ্ছেদ শিরোনাম এবং সারণি পরীক্ষা করা হয়। '
    'কম্পিউটারে লেখা নথি থেকে পাঠ্য উদ্ধার করলে মূল শব্দগুলো অপরিবর্তিত থাকা দরকার। '
    'এই উদাহরণে কোনো বাস্তব গবেষণার ফল দাবি করা হচ্ছে না। '
    'এটি কেবল বাংলা মুদ্রণ ও সম্পাদনার একটি পরীক্ষামূলক নমুনা।'
)


def make_source(kind: str, pages: int, memo: bool):
    if pages not in (1, 10, 100) or type(memo) is not bool:
        raise ValueError('pages must be 1, 10 or 100 and memo must be Boolean')
    if kind in ('distinct', 'repeated'):
        return perf.source(pages, 96, kind, memo)
    if kind == 'digits-free':
        src, spec, old = perf.source(pages, 96, 'distinct', memo)
        syllables = ['ক','খ','গ','ঘ','কা','কি','কু','কে','ক্র','প্র','গ্র','ত্র','ক্ষ','জ্ঞ','দ্ব','স্ব']
        words = [''.join(syllables[(i//(16**j))%16] for j in range(4)) for i in range(96*pages)]
        # Deliberately fixed known fixture, never arbitrary user-source parsing.
        mapping = dict(zip(old,words))
        src = re.sub('|'.join(map(re.escape,sorted(mapping,key=len,reverse=True))), lambda m:mapping[m[0]],src)
        spec.update(workload='Distinct four-component strings; no digits; not dictionary words.',
                    source_sha256=perf.sha(src.encode()),mode=kind)
        return src,spec,words
    if kind not in ('prose', 'varied-prose'):
        raise ValueError('unknown fixture')
    passages = [PROSE]
    if kind == 'varied-prose':
        data = json.loads((Path(__file__).resolve().parents[1]/'examples/benchmark-prose-v1.json').read_text(encoding='utf8'))
        passages = data['paragraphs']
        if data['schema'] != 1 or len(passages) != 10 or any(type(t) is not str or not t or len(t.encode('utf8')) > 4096 or any(c in t for c in '{}\\%') for t in passages):
            raise ValueError('invalid bounded literal prose fixture')
    lines = [r'\documentclass[11pt]{article}',r'\usepackage[margin=25mm]{geometry}',r'\usepackage{bntex-native}']
    if memo:
        lines.append(r'\usepackage{bntex-native-memo}')
    lines += [r'\BnTeXNativeLoadProfile{bntex-native-profile.tex}',r'\begin{document}',
              r'\ifnum\pdfshellescape=0\else\errmessage{shell enabled}\fi',r'\raggedright']
    for i in range(pages):
        lines += [r'\noindent\bnNative{'+passages[i % len(passages)]+r'}\clearpage']
    lines.append(r'\end{document}')
    src='\n'.join(lines)+'\n'; words=[w for i in range(pages) for w in passages[i % len(passages)].split()]
    spec={'pages_requested':pages,'token_occurrences':len(words),'distinct_tokens':len(set(words)),
          'source_sha256':perf.sha(src.encode()),'mode':kind,'memo_enabled':memo,
          'workload':('Ten different authored paragraphs, cycling only beyond ten pages; not reviewed or representative book prose.' if kind == 'varied-prose' else 'Original authored prose fixture repeated per page; not corpus-derived or independent user acceptance.')}
    return src,spec,words


def probe_source():
    words = ['কর্ম','প্রযুক্তি','গবেষণা','কো','ড়','স্বাস্থ্য','ত্রিমাত্রিক','ক্\u200dষ']*8
    instrumentation = r'''\ExplSyntaxOn
\int_new:N\g__bndp_calls_int
\int_new:N\g__bndp_decode_int
\int_new:N\g__bndp_render_int
\int_new:N\g__bndp_total_int
\int_new:N\l__bndp_start_int
\int_new:N\l__bndp_render_start_int
\cs_new_eq:NN\__bndp_decode:nTF\bntex_utfviii_decode:nTF
\cs_set_protected:Npn\bntex_utfviii_decode:nTF#1#2#3
 {\int_gincr:N\g__bndp_calls_int\int_set:Nn\l__bndp_start_int{\pdfelapsedtime}
  \__bndp_decode:nTF{#1}
   {\int_gadd:Nn\g__bndp_decode_int{\pdfelapsedtime-\l__bndp_start_int}#2}
   {\int_gadd:Nn\g__bndp_decode_int{\pdfelapsedtime-\l__bndp_start_int}#3}}
\cs_new_eq:NN\__bndp_render:\__bn_render:
\cs_set_protected:Npn\__bn_render:
 {\group_begin:\int_set:Nn\l__bndp_render_start_int{\pdfelapsedtime}
  \__bndp_render:\int_gadd:Nn\g__bndp_render_int{\pdfelapsedtime-\l__bndp_render_start_int}\group_end:}
\ExplSyntaxOff'''
    src=(r'\documentclass{article}\usepackage{bntex-native}\BnTeXNativeLoadProfile{bntex-native-profile.tex}'+'\n'+instrumentation+
         '\n'+r'\begin{document}\ExplSyntaxOn\int_gset:Nn\g__bndp_total_int{\pdfelapsedtime}\ExplSyntaxOff'+'\n')
    src+='\n'.join(r'\bnNative{'+' '.join(words[i:i+8])+'}' for i in range(0,len(words),8))
    src+='\n'+r'\ExplSyntaxOn\int_gset:Nn\g__bndp_total_int{\pdfelapsedtime-\g__bndp_total_int}'
    src+=''.join(r'\iow_term:x{DECODEPROBE|'+n+r'|\int_use:N\g__bndp_'+n+'_int}' for n in ('calls','decode','render','total'))
    src+=r'\ExplSyntaxOff\end{document}'+'\n'
    return src, words


def run_pair(baseline: Path,candidate: Path,out: Path,*,pages=(1,10),kinds=('distinct',),repetitions=3,memo=False,timeout=600,probe=False):
    if not 1<=repetitions<=5 or len(set(pages))!=len(pages) or len(set(kinds))!=len(kinds):
        raise ValueError('invalid or duplicate workload/repetition arguments')
    loaded = {name:perf.installation(path) for name,path in [('baseline',baseline),('candidate',candidate)]}
    for prop in ('font_sha256','profile_sha256'):
        if loaded['baseline'][1].get(prop)!=loaded['candidate'][1].get(prop):
            raise ValueError('paired font/profile identities differ')
    if out.exists() or any(p.is_symlink() for p in (out,*out.parents)):
        raise ValueError('output must be new and have no symlink ancestors')
    out.mkdir(parents=True)
    report={'schema':1,'baseline_identity':'See installation hashes; source revision is supplied by the operator, not inferred.',
            'measurement':'Fresh pdfTeX process per sample. Alternating version order. OS caches not flushed. Shared-host timing.',
            'memo_enabled':memo,'installations':{n:m for n,(_,m) in loaded.items()},'rows':[],'probes':[]}
    def save():
        (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for kind in kinds:
        for count in pages:
            src,spec,words=make_source(kind,count,memo)
            samples={name:[] for name in loaded}; row={'fixture':spec,'samples':samples};report['rows'].append(row)
            for rep in range(repetitions):
                order=('baseline','candidate') if rep%2==0 else ('candidate','baseline')
                for name in order:
                    target=out/f'{kind}-{count}-{rep}-{name}';target.mkdir()
                    for file,raw in loaded[name][0].items(): (target/file).write_bytes(raw)
                    (target/'main.tex').write_text(src,encoding='utf8')
                    result=perf.compile_run(target,loaded[name][0],words,1,timeout)
                    result.update(repetition=rep+1,source_sha256=spec['source_sha256'])
                    if result['status']=='compiled' and result['pdf_pages']!=count:
                        result['status']='page-count-error'
                    samples[name].append(result);save()
                    print(kind,count,rep+1,name,result['status'],result['runs'][0]['wall_seconds'],flush=True)
            row['all_pairs_pdf_identical']=all(a.get('status')==b.get('status')=='compiled' and a.get('pdf_sha256')==b.get('pdf_sha256') for a,b in zip(samples['baseline'],samples['candidate']))
            row['summary']={}
            for name,records in samples.items():
                times=[r['runs'][0]['wall_seconds'] for r in records if r['status']=='compiled']
                row['summary'][name]={'successful_samples':len(times),'median_seconds':statistics.median(times) if times else None,
                                      'min_seconds':min(times) if times else None,'max_seconds':max(times) if times else None}
            save()
    if probe:
        src,words=probe_source()
        for name in loaded:
            target=out/f'probe-{name}';target.mkdir()
            for file,raw in loaded[name][0].items(): (target/file).write_bytes(raw)
            (target/'main.tex').write_text(src,encoding='utf8')
            result=perf.compile_run(target,loaded[name][0],words,1,timeout)
            log=(target/'main.log').read_text(errors='replace')
            result['ticks']={key:int(value) for key,value in re.findall(r'DECODEPROBE\|(\w+)\|(\d+)',log)}
            report['probes'].append({'version':name,**result});save()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--pages',type=int,nargs='+',choices=(1,10,100),default=[1,10])
    p.add_argument('--kinds',nargs='+',choices=('distinct','repeated','digits-free','prose','varied-prose'),default=['distinct'])
    p.add_argument('--repetitions',type=int,choices=range(1,6),default=3)
    p.add_argument('--memo',action='store_true');p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--probe',action='store_true')
    a=p.parse_args()
    try:
        r=run_pair(a.baseline,a.candidate,a.out,pages=a.pages,kinds=a.kinds,repetitions=a.repetitions,memo=a.memo,timeout=a.timeout,probe=a.probe)
        return 0 if all(row['all_pairs_pdf_identical'] for row in r['rows']) and all(x['status']=='compiled' for x in r['probes']) else 1
    except (ValueError,OSError,KeyError) as exc:
        print(f'benchmark error: {exc}',file=sys.stderr);return 2

if __name__=='__main__':
    raise SystemExit(main())
