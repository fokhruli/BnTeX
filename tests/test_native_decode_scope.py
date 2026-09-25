"""Lifetime of private decoded word records; public decoder is unchanged."""
from test_native_decode_once import (native_install, tex_profile, run_tex, SNAPSHOT, COUNT_DECODE,
                                    sliced, expected_slice)

def test_original_decoder_sink_is_restored(native_install):
    body = r'''\ExplSyntaxOn
\cs_new_eq:NN\__test_saved_sink:\__bntex_utfviii_emit:
\ExplSyntaxOff
\bnNative{কর্ম তথ্য}
\ExplSyntaxOn
\cs_if_eq:NNF\__test_saved_sink:\__bntex_utfviii_emit:{\errmessage{decoder sink leaked}}
\cs_if_exist:cT{l__bn_span_1_scalars_seq}{\errmessage{word record leaked}}
\ExplSyntaxOff'''
    run_tex(native_install,body)

def test_word_records_are_rebuilt_for_later_spans(native_install):
    spans=['কর্ম তথ্য গবেষণা','কো কো','প্রযুক্তি']
    out,_=run_tex(native_install,''.join(r'\bnNative{'+s+'}' for s in spans),preamble=SNAPSHOT+COUNT_DECODE)
    assert sliced(out)==[expected_slice(w) for s in spans for w in s.split()]
