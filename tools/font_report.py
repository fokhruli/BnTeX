#!/usr/bin/env python3
"""Inventory a local font's layout tables; emits metadata, not a font file."""
import argparse
from collections import Counter
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from bntex.build import inspect_font


def report(path: Path) -> dict:
    result=inspect_font(path)
    with TTFont(path) as font:
        result['table_tags']=sorted(font.keys())
        for tag in ('GSUB','GPOS'):
            if tag not in font:
                result[tag]=None;continue
            table=font[tag].table
            lookups=table.LookupList.Lookup if table.LookupList else []
            feature_records=table.FeatureList.FeatureRecord if table.FeatureList else []
            result[tag]={
                'lookup_types':dict(Counter(str(x.LookupType) for x in lookups)),
                'lookups':[{'index':i,'type':x.LookupType,'flags':x.LookupFlag,
                  'subtable_formats':[getattr(y,'Format',None) for y in x.SubTable],
                  'extension_types':[getattr(y,'ExtensionLookupType',None) for y in x.SubTable]}
                    for i,x in enumerate(lookups)],
                'features':[{'tag':x.FeatureTag,'lookup_indices':x.Feature.LookupListIndex}
                    for x in feature_records],
                'scripts':[{ 'tag':r.ScriptTag,
                    'languages':[x.LangSysTag for x in r.Script.LangSysRecord],
                    'default_language':r.Script.DefaultLangSys is not None}
                    for r in (table.ScriptList.ScriptRecord if table.ScriptList else [])],
            }
    result['scope']='Inventory only: not a native-profile support/closure validator.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('font',type=Path)
    args=p.parse_args()
    print(json.dumps(report(args.font),ensure_ascii=False,indent=2))
