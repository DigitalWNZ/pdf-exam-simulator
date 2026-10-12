from exam_sim.parser.bilingual import answer_letters, english_tail, has_cjk, is_bilingual, parse_bilingual
from exam_sim.parser.extract import Line


def L(*texts):
    return [Line(t, 1) for t in texts]


def test_has_cjk_includes_kangxi_radicals():
    assert has_cjk("你应该怎么做？") and has_cjk("⼀个")     # '⼀' is U+2F00 (Kangxi radical)
    assert not has_cjk("Use tf.distribute.TPUStrategy (Choose two.)")


def test_english_tail_is_trailing_non_cjk_run():
    tail = english_tail(L("使⽤", "tf.distribute.MirroredStrategy进⾏分发。", "Use MirroredStrategy", "for distribution."))
    assert [l.text for l in tail] == ["Use MirroredStrategy", "for distribution."]


def test_answer_letters_matches_option_text_including_multi():
    opts = [("A", "Alpha thing"), ("B", "Beta thing"), ("C", "Gamma"), ("D", "Delta stuff"), ("E", "Eps more")]
    assert answer_letters("D. Delta stuff E. Eps more", opts) == ["D", "E"]
    assert answer_letters("B. Beta thing", opts) == ["B"]
    assert answer_letters("C. something unmatched", [("A", "x"), ("B", "y")]) == ["C"]


def test_parse_bilingual_question():
    lines = L("Title Part 1", "问题 1", "题⽬", "你应该怎么做？", "What should", "you do?", "选项",
              "A. 选A", "Pick A", "B. 选B", "Pick B", "C. 选C", "Pick C", "continued",
              "正确答案：C. Pick C continued", "解析： 因为C。", "A. 不是选项", "问题 2", "题⽬", "问?", "Q2?", "选项",
              "A. 甲", "One", "B. 乙", "Two", "正确答案：A. One")
    assert is_bilingual(lines)
    q1, q2 = parse_bilingual(lines)
    assert q1.number == 1 and [l.text for l in q1.stem_parts] == ["What should", "you do?"]
    assert [o.letter for o in q1.options] == ["A", "B", "C"]
    assert [l.text for l in q1.options[2].parts] == ["Pick C", "continued"]
    assert q1.pdf_answer == ["C"]
    assert q2.number == 2 and q2.pdf_answer == ["A"] and len(q2.options) == 2
