import pytest
from bntex.harfbuzz import HarfBuzz
from bntex.build import inspect_font

CORPUS=['ক্ষ','জ্ঞ','স্বাস্থ্য','প্রযুক্তি','স্বাধীনতা','কি','কী','কু','কূ','কৃ','কে','কৈ','কো','কৌ',
        'কাঁ','কর্ম','ধর্ম','অর্থ','সূর্য','দৃষ্টি','ড়','ঢ়','য়','০১২৩৪৫৬৭৮৯','বাংলা।','ক্\u200dষ','ক্\u200cষ']

@pytest.mark.integration
@pytest.mark.parametrize('style',['regular','bold','sans'])
def test_corpus_shapes_with_byte_clusters(fonts,style):
    meta=inspect_font(fonts[style])
    with HarfBuzz(fonts[style]) as hb:
        assert hb.upem==meta['upem']
        for word in CORPUS:
            run=hb.shape(word)
            offsets={len(word[:i].encode('utf8')) for i in range(len(word))}
            assert run and sum(g.x_advance for g in run)>0
            assert all(g.cluster in offsets and 0<g.gid<meta['glyph_count'] for g in run)
            assert all(g.y_advance==0 for g in run)
            assert run==hb.shape(word)

@pytest.mark.integration
def test_invalid_or_missing_glyph_and_closed_font(fonts):
    hb=HarfBuzz(fonts['regular'])
    for bad in ['', '\x00', 'ক'*4097, '\U0010ffff']:
        with pytest.raises(ValueError): hb.shape(bad)
    hb.close();hb.close()
    with pytest.raises(RuntimeError): hb.shape('ক')
