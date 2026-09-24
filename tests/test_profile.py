"""Small synthetic OpenType graphs plus real local-font integration tests."""
from types import SimpleNamespace as N
import json
import pytest
from bntex.profile import audit_layout, audit_font
from bntex.__main__ import main


def lookup(kind=1, refs=(), flags=0, **kwargs):
    sub = N(Format=1, SubstLookupRecord=[N(LookupListIndex=i, SequenceIndex=0) for i in refs])
    return N(LookupType=kind, LookupFlag=flags, SubTable=[sub], **kwargs)


def layout(lookups, root=0, required=0xFFFF):
    lang = N(FeatureIndex=[0], ReqFeatureIndex=required)
    script = N(DefaultLangSys=lang, LangSysRecord=[])
    feature = N(FeatureTag='ccmp', Feature=N(LookupListIndex=[root]))
    return N(LookupList=N(Lookup=lookups), FeatureList=N(FeatureRecord=[feature]),
             ScriptList=N(ScriptRecord=[N(ScriptTag='bng2', Script=script)]))


def test_nested_only_lookup_closure_and_unreachable_nodes():
    table = layout([lookup(6, [1]), lookup(6, [2]), lookup(), lookup(4)])
    report = audit_layout(table, 'GSUB')
    assert report['root_lookups'] == [0]
    assert report['reachable_lookups'] == [0, 1, 2]
    assert report['nested_only_lookups'] == [1, 2]
    assert report['unreachable_lookups'] == [3]
    assert report['cycle_back_edges'] == []


@pytest.mark.parametrize('tag,extension,context', [('GSUB', 7, 6), ('GPOS', 9, 8)])
def test_extension_context_reference_is_followed(tag, extension, context):
    outer = lookup(extension)
    outer.SubTable = [N(Format=1, ExtensionLookupType=context, ExtSubTable=lookup(context, [1]).SubTable[0])]
    report = audit_layout(layout([outer, lookup()]), tag)
    assert report['nested_only_lookups'] == [1]
    assert report['lookups'][0]['subtables'][0]['effective_type'] == context


def test_cycles_are_bounded_and_reported_not_executed():
    report = audit_layout(layout([lookup(6, [1]), lookup(6, [0])]), 'GSUB')
    assert report['cycle_back_edges'] == [[1, 0]]


@pytest.mark.parametrize('bad', [-1, 2, '1', True])
def test_bad_nested_reference_is_rejected(bad):
    with pytest.raises(ValueError, match='nested lookup: invalid index'):
        audit_layout(layout([lookup(6, [bad]), lookup()]), 'GSUB')


def test_bad_required_feature_is_rejected():
    with pytest.raises(ValueError, match='feature: invalid index'):
        audit_layout(layout([lookup()], required=9), 'GSUB')


def test_no_matching_script_is_explicit_not_a_support_claim():
    report = audit_layout(layout([lookup()]), 'GSUB', ('latn',))
    assert report['selected_systems'] == []
    assert report['reachable_lookups'] == []
    assert report['unreachable_lookups'] == [0]


@pytest.mark.parametrize('kind', [7, 0, 99])
def test_invalid_extension_type_is_rejected(kind):
    outer = lookup(7)
    outer.SubTable = [N(Format=1, ExtensionLookupType=kind, ExtSubTable=N(Format=1))]
    with pytest.raises(ValueError, match='malformed extension'):
        audit_layout(layout([outer]), 'GSUB')


def test_mixed_extension_types_are_rejected():
    outer = lookup(7)
    outer.SubTable = [N(Format=1, ExtensionLookupType=i, ExtSubTable=N(Format=1)) for i in (1, 2)]
    with pytest.raises(ValueError, match='mixed effective'):
        audit_layout(layout([outer]), 'GSUB')


def test_mark_filter_dependencies_and_index():
    table = layout([lookup(flags=0x10, MarkFilteringSet=0)])
    with pytest.raises(ValueError, match='GDEF.GlyphClassDef'):
        audit_layout(table, 'GSUB')
    gdef = N(GlyphClassDef=N(), MarkGlyphSetsDef=N(Coverage=[N()]))
    report = audit_layout(table, 'GSUB', gdef=gdef)
    assert report['lookups'][0]['mark_filtering_set'] == 0
    table.LookupList.Lookup[0].MarkFilteringSet = 1
    with pytest.raises(ValueError, match='MarkFilteringSet'):
        audit_layout(table, 'GSUB', gdef=gdef)


def test_reserved_lookup_flags_rejected():
    with pytest.raises(ValueError, match='reserved lookup flags'):
        audit_layout(layout([lookup(flags=0x20)]), 'GSUB')


def test_feature_roots_include_all_language_systems_and_required_features():
    table = layout([lookup(), lookup()], required=0)
    table.FeatureList.FeatureRecord.append(N(FeatureTag='locl', Feature=N(LookupListIndex=[1])))
    table.ScriptList.ScriptRecord[0].Script.LangSysRecord.append(
        N(LangSysTag='BEN ', LangSys=N(ReqFeatureIndex=1, FeatureIndex=[])))
    result = audit_layout(table, 'GSUB')
    assert result['root_lookups'] == [0, 1]
    assert result['selected_systems'][1]['features'][0]['required']


def test_bad_original_table_header():
    with pytest.raises(ValueError, match='truncated'):
        audit_layout(layout([lookup()]), 'GSUB', raw=b'\0')


@pytest.mark.integration
@pytest.mark.parametrize('style', ['regular', 'bold', 'sans'])
def test_local_font_audit_is_deterministic_and_not_native_support(fonts, style):
    first = audit_font(fonts[style])
    second = audit_font(fonts[style])
    assert first == second
    assert first['native_runtime_supported'] is False
    assert first['kind'] == 'bntex-structural-layout-audit'
    assert len(first['font']['sha256']) == 64
    assert first['tables']['GSUB']['selected_systems']
    for table in first['tables'].values():
        if table is None:
            continue
        ids = table['reachable_lookups']
        assert len(ids) == len(set(ids))
        assert set(table['root_lookups']) <= set(ids)
        for item in table['lookups']:
            assert set(item['references']) <= set(ids)
            for sub in item['subtables']:
                assert sub['effective_format'] in (1, 2, 3)


@pytest.mark.integration
def test_profile_cli(fonts, capsys):
    assert main(['profile', '--font', str(fonts['regular'])]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['native_runtime_supported'] is False
    assert main(['profile', '--font', str(fonts['regular']), '--script', 'Bengali']) == 2
    assert 'four ASCII' in capsys.readouterr().err
