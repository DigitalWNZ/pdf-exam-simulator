from exam_sim.parser.blocks import join_lines, parse_questions
from exam_sim.parser.extract import Line
from tests.parser.helpers import image, lines


def q(*texts):
    return parse_questions(lines(*texts))


def test_join_lines_wraps_with_spaces_and_keeps_numbered_steps():
    assert join_lines(["You need to", "do X.", "1. First", "step continues", "2. Second"]) == \
        "You need to do X.\n1. First step continues\n2. Second"
    assert join_lines(["  ", "a", ""]) == "a"


def test_single_question_basic_shape():
    [raw] = q("Question #1", "Topic 1", "Stem line one", "continues here.",
              "A. Threading", "B. Serialization", "C. Dropout", "Most Voted", "D. Reduction",
              "Correct Answer: C", "Community vote distribution", "C (100%)")
    assert raw.number == 1 and raw.topic == "1" and raw.page == 1
    assert [l.text for l in raw.stem_parts] == ["Stem line one", "continues here."]
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [o.most_voted for o in raw.options] == [False, False, True, False]
    assert [l.text for l in raw.options[2].parts] == ["Dropout"]
    assert raw.pdf_answer == ["C"]
    assert [(v.letters, v.pct) for v in raw.votes] == [(["C"], 100)]
    assert raw.stray == []


def test_out_of_sequence_letter_is_continuation_text():
    [raw] = q("Question #2", "Stem", "A. First", "B. Second mentions", "D. not an option yet",
              "C. Third", "D. Fourth", "Correct Answer: A")
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [l.text for l in raw.options[1].parts] == ["Second mentions", "D. not an option yet"]
    assert raw.relabeled == {}


def test_wrapped_line_starting_with_earlier_letter_is_text():
    # Q236 in the real PDF: option C wraps as "...read replica in region" / "B. Scale up read workloads..."
    [raw] = q("Question #236", "Stem", "A. a", "B. b", "C. replica in region", "B. Scale up read workloads.",
              "D. d", "Correct Answer: C")
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [l.text for l in raw.options[2].parts] == ["replica in region", "B. Scale up read workloads."]
    assert raw.relabeled == {}


def test_mislabeled_option_letter_is_renumbered_and_key_remapped():
    # Q224 in the real PDF: option C is printed as "G." and the key and votes say G as well.
    [raw] = q("Question #224", "Stem", "A. a", "B. b", "wrapped b", "G. c", "wrapped c", "Most Voted", "D. d",
              "Correct Answer: G", "Community vote distribution", "G (89%)", "B (11%)")
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [l.text for l in raw.options[1].parts] == ["b", "wrapped b"]
    assert [l.text for l in raw.options[2].parts] == ["c", "wrapped c"]
    assert [o.most_voted for o in raw.options] == [False, False, True, False]
    assert raw.relabeled == {"G": "C"}
    assert raw.pdf_answer == ["C"]
    assert [(v.letters, v.pct) for v in raw.votes] == [(["C"], 89), (["B"], 11)]


def test_mislabel_lookahead_stops_at_the_next_question():
    raws = q("Question #1", "S", "A. a", "B. b", "G. c", "Correct Answer: G",
             "Question #2", "S", "A. a", "B. b", "C. c", "Correct Answer: C")
    assert [o.letter for o in raws[0].options] == ["A", "B", "C"] and raws[0].relabeled == {"G": "C"}
    assert [o.letter for o in raws[1].options] == ["A", "B", "C"] and raws[1].relabeled == {}


def test_multi_answer_and_multiple_most_voted():
    [raw] = q("Question #10", "Stem (Choose three)", "A. a", "B. b", "Most Voted", "C. c", "D. d",
              "Most Voted", "E. e", "Most Voted", "F. f", "Correct Answer: BDE",
              "Community vote distribution", "BDE (90%)", "BCD (10%)")
    assert raw.pdf_answer == ["B", "D", "E"]
    assert [o.letter for o in raw.options if o.most_voted] == ["B", "D", "E"]
    assert [(v.letters, v.pct) for v in raw.votes] == [(["B", "D", "E"], 90), (["B", "C", "D"], 10)]


def test_inline_most_voted_suffix():
    [raw] = q("Question #3", "Stem", "A. x Most Voted", "B. y", "wrapped Most Voted", "Correct Answer: A")
    assert raw.options[0].most_voted and [l.text for l in raw.options[0].parts] == ["x"]
    assert raw.options[1].most_voted and [l.text for l in raw.options[1].parts] == ["y", "wrapped"]


def test_images_attach_to_stem_or_open_option():
    img1, img2 = image(page=1), image(page=1)
    items = lines("Question #9", "Topic 1", "Error:") + [img1] + lines("Which?", "A.") + [img2] + \
        lines("B. text", "Correct Answer: A")
    [raw] = parse_questions(items)
    assert raw.stem_parts == [Line("Error:", 1), img1, Line("Which?", 1)]
    assert raw.options[0].parts == [img2]
    assert [l.text for l in raw.options[1].parts] == ["text"]


def test_image_after_answer_is_stray():
    img = image()
    [raw] = parse_questions(lines("Question #4", "Stem", "A. a", "Correct Answer: A") + [img])
    assert raw.stray == [img]


def test_no_vote_section_and_stray_lines():
    [raw] = q("Question #321", "Stem", "A. a", "B. b", "Correct Answer: B", "Some unexpected line")
    assert raw.votes == [] and [s.text for s in raw.stray] == ["Some unexpected line"]


def test_votes_continue_across_page_break_and_multiple_questions():
    items = lines("Question #243", "Stem", "A.", "B.", "Correct Answer: C", "Community vote distribution", page=201) + \
        lines("C (52%)", "A (48%)", "Question #244", "Stem2", "A. a", "Correct Answer: A", page=202)
    raws = parse_questions(items)
    assert [r.number for r in raws] == [243, 244]
    assert [(v.letters, v.pct) for v in raws[0].votes] == [(["C"], 52), (["A"], 48)]
    assert raws[1].page == 202


def test_several_vote_entries_on_one_line():
    [raw] = q("Question #18", "Stem", "A. a", "B. b", "Correct Answer: BDE", "Community vote distribution",
              "BDE (89%)", "BCE (5%)CDE (3%)ACD (3%)", "BC (7%) BE (3%)")
    assert [("".join(v.letters), v.pct) for v in raw.votes] == \
        [("BDE", 89), ("BCE", 5), ("CDE", 3), ("ACD", 3), ("BC", 7), ("BE", 3)]
    assert raw.stray == []


def test_option_text_with_numbered_steps_stays_in_option():
    [raw] = q("Question #5", "Stem", "A. 1. Export metadata.", "2. Implement metastore.", "B. 1. Use Dataplex.",
              "Correct Answer: B")
    assert [l.text for l in raw.options[0].parts] == ["1. Export metadata.", "2. Implement metastore."]
    assert [l.text for l in raw.options[1].parts] == ["1. Use Dataplex."]


def test_topic_is_optional_and_lines_before_first_question_are_ignored():
    [raw] = q("junk", "Question #7", "Stem only", "A. a", "Correct Answer: A")
    assert raw.topic is None and [l.text for l in raw.stem_parts] == ["Stem only"]
