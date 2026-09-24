#!/usr/bin/env python3
"""Bounded 1/10/100-page native benchmarks; report timeouts, never extrapolate.

Each page contains 200 tokens. Distinct tokens are synthetic well-formed syllable
strings, not a corpus of dictionary-approved words. Recompilation is a fresh TeX
process with warm auxiliary files, not a warm persistent word cache.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import random
import shutil
import sys

from bntex.native_project import compile_once, installation_manifest

VOCABULARY='বাংলা ভাষা শিক্ষা গবেষণা প্রযুক্তি পদ্ধতি তথ্য পরীক্ষা ফলাফল সমাজ মানুষ কাজ উন্নতি নতুন পরিকল্পনা বিজ্ঞান গণিত বিশ্ববিদ্যালয় ব্যবহার পরিবর্তন'.split()
SYLLABLES=['কা','কি','কু','কে','গা','গি','গু','গে','না','নি','নু','নে','মা','মি','মু','মে']


def tokens(pages, workload):
    count=200*pages
    if workload=='repeated': return [VOCABULARY[i%len(VOCABULARY)] for i in range(count)]
    if workload!='distinct': raise ValueError('Unknown workload')
    # A permutation makes adjacent words less alike, without unbounded rejection.
    indices=random.Random(703).sample(range(16**4),count)
    return [''.join(SYLLABLES[(i//(16**j))%16] for j in range(4)) for i in indices]


def source(pages, workload, memo):
    words=tokens(pages,workload)
    lines=[r'\documentclass[12pt]{article}',r'\usepackage[a4paper,margin=25mm]{geometry}',
        r'\usepackage{bntex-native-memo}',r'\BnTeXNativeLoadProfile{bntex-native-profile.tex}',
        r'\setlength{\parindent}{0pt}',r'\setlength{\parskip}{5pt}',r'\tracingstats=1',
        r'\begin{document}',r'\ifnum\pdfshellescape=0\else\errmessage{shell enabled}\fi']
    if not memo:lines.append(r'\BnTeXNativeMemoOff')
    for page in range(pages):
        if page:lines.append(r'\newpage')
        lines.append(f'Native stress page {page+1} / {pages} ({workload}).\\par')
        for start in range(page*200,(page+1)*200,40):
            lines.append('\\bnNative{'+' '.join(words[start:start+40])+'}\\par')
    lines += [r'\BnTeXNativeMemoStats',r'\end{document}']
    return '\n'.join(lines)+'\n',words


def one(installation,out,pages,workload,memo,timeout,passes):
    name=f'{pages:03d}-{workload}-'+('memo' if memo else 'uncached')
    directory=out/name;directory.mkdir()
    inst=installation_manifest(installation)
    for path in [*inst['files'],'native-installation.json']:shutil.copyfile(installation/path,directory/path)
    code,words=source(pages,workload,memo);(directory/'main.tex').write_text(code,encoding='utf-8')
    result={'case':name,'requested_pages':pages,'tokens':len(words),'distinct_tokens':len(set(words)),
            'workload':workload,'synthetic_tokens':workload=='distinct','memo_enabled':memo,
            'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'runs':[]}
    for i in range(passes):
        row=compile_once(directory,'main.tex',timeout=timeout,tag=f'pass-{i+1}')
        text=row.pop('extracted_text','');row.pop('pdf_info',None)
        if row['status']=='success':
            row['expected_page_count']=row['pages']==pages
            row['all_distinct_tokens_extracted']=all(w in text for w in set(words))
            if not row['expected_page_count'] or not row['all_distinct_tokens_extracted']:row['status']='validation-error'
        result['runs'].append(row)
        if row['status']!='success':break
    installation_manifest(directory)
    result['installation_intact']=True
    # Reports/PDFs remain; erase copied font installation, never distribute fonts.
    for path in [*inst['files'],'native-installation.json']:(directory/path).unlink()
    (directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installation',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pages',type=int,nargs='+',default=[1,10,100]);p.add_argument('--timeout',type=float,default=60)
    p.add_argument('--passes',type=int,default=2);p.add_argument('--workers',type=int,default=1)
    p.add_argument('--workloads',nargs='+',choices=['repeated','distinct'],default=['repeated','distinct'])
    p.add_argument('--modes',nargs='+',choices=['memo','uncached'],default=['uncached','memo'])
    a=p.parse_args(argv)
    try:
        if a.out.exists() or a.out.is_symlink():raise ValueError('Output must be new')
        if any(n not in (1,10,100) for n in a.pages) or not 1<=a.passes<=2 or not 1<=a.workers<=2:raise ValueError('Unsupported benchmark bounds')
        installation_manifest(a.installation);a.out.mkdir(parents=True)
        cases=list(itertools.product(a.pages,a.workloads,a.modes))
        # workers=1 is recommended for comparable timings. Parallel runs are
        # explicitly identified and must not be compared to uncontended timings.
        def execute(c):return one(a.installation,a.out,c[0],c[1],c[2]=='memo',a.timeout,a.passes)
        rows=[]
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            for row in pool.map(execute,cases):
                rows.append(row);print(row['case'],[r['status'] for r in row['runs']],flush=True)
                (a.out/'results.json').write_text(json.dumps({'schema':1,'workers':a.workers,
                    'timing_note':'fresh processes; auxiliary files warm on pass 2; timeout rows are incomplete',
                    'results':rows},ensure_ascii=False,indent=2)+'\n')
        return 0 # A timeout is a measured result, not a falsely successful compile.
    except (OSError,ValueError,KeyError) as e:print(e,file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
