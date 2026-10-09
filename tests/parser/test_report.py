from exam_sim.parser.assemble import build_question
from exam_sim.parser.blocks import RawOption, RawQuestion, parse_questions
from exam_sim.parser.extract import Line
from exam_sim.parser.model import ImageBlock, Option, Question, TextBlock, Vote
from exam_sim.parser.report import build_report, format_report
from tests.parser.helpers import lines


def mk(number, options="ABCD", answer=("A",), pdf=None, votes=(), stem="Stem?", disputed=False, source="votes",
       stem_blocks=None):
    return Question(number=number, topic="1",
                    stem=stem_blocks or [TextBlock(text=stem)],
                    options=[Option(letter=l, content=[TextBlock(text=l)]) for l in options],
                    answer=list(answer), select_count=len(answer),
                    pdf_answer=list(pdf if pdf is not None else answer),
                    votes=list(votes), answer_source=source, disputed=disputed)


def test_report_counts_and_errors():
    qs = [mk(1), mk(2, options="", answer=()), mk(4, answer=("Z",)), mk(4),
          mk(5, stem="Pick two (Choose two)", answer=("A",)), mk(6, options="ABCDE", answer=("A", "B"))]
    r = build_report(qs, [])
    assert r.question_count == 6 and (r.first_number, r.last_number) == (1, 6)
    assert r.missing_numbers == [3] and r.duplicate_numbers == [4]
    assert r.option_histogram == {0: 1, 4: 4, 5: 1}
    assert r.no_options == [2] and r.no_answer == [2] and r.answer_not_in_options == [4]
    assert r.choose_hint_mismatch == [(5, 2, 1)]
    assert r.no_votes == 6
    assert len(r.errors()) == 3
    text = format_report(r)
    assert "questions: 6 (#1–#6)" in text and "missing numbers: [3]" in text and "errors:" in text


def test_report_images_disputed_most_voted_and_stray():
    raw = RawQuestion(number=7, page=3, options=[RawOption("A", most_voted=True), RawOption("B")],
                      stray=[Line("odd", 3)])
    q = mk(7, answer=("B",), pdf=("A",), disputed=True, votes=[Vote(["B"], 100)],
           stem_blocks=[TextBlock(text="S"), ImageBlock(src="images/q007_1.png", w=1, h=1)])
    r = build_report([q], [raw], warnings=["Q7: image 2 could not be converted"])
    assert r.image_blocks == 1 and r.no_votes == 0
    assert r.disputed == [(7, "B", "A", "votes")]
    assert r.most_voted_mismatch == [(7, "A", "B")]
    assert r.stray == [(7, 3, "odd")]
    assert r.errors() == []
    text = format_report(r)
    assert "Q7 key=B pdf=A [votes]" in text and "warning: Q7: image 2" in text and "errors: none" in text


def test_empty_report():
    r = build_report([], [])
    assert r.question_count == 0 and r.errors() == []
    assert "questions: 0" in format_report(r)
    assert "relabeled option letters: none" in format_report(r)


def test_report_lists_relabeled_option_letters():
    raw = RawQuestion(number=224, page=183, options=[RawOption(l) for l in "ABCD"], relabeled={"G": "C"})
    r = build_report([mk(224, answer=("C",))], [raw])
    assert r.relabeled == [(224, "G", "C")]
    assert r.errors() == []
    assert "relabeled option letters: Q224 G→C" in format_report(r)


def test_relabel_colliding_with_a_real_option_letter_is_an_error():
    # Forward duplicate-letter typo: "D." printed twice. The source is ambiguous, so strict mode must fail.
    raws = parse_questions(lines("Question #5", "S", "A. a", "B. b", "D. c-typo", "D. d-real", "Correct Answer: D",
                                 "Community vote distribution", "D (89%)", "B (11%)"))
    qs = [build_question(raw, lambda img: None) for raw in raws]
    r = build_report(qs, raws)
    assert r.relabeled == [(5, "D", "C")] and r.ambiguous_relabel == [5]
    assert r.errors() == ["ambiguous option relabel (PDF letter is also a real option): [5]"]
    assert "errors: ambiguous option relabel" in format_report(r)
