from exam_sim.parser.assemble import assemble_blocks, build_question
from exam_sim.parser.blocks import RawOption, RawQuestion
from exam_sim.parser.extract import Image
from exam_sim.parser.images import MISSING_IMAGE_TEXT, ImageWriter
from exam_sim.parser.model import ImageBlock, TextBlock, Vote
from tests.parser.helpers import image, lines


def test_assemble_blocks_joins_text_and_places_images(tmp_path):
    writer = ImageWriter(tmp_path / "bank")
    img = image(50, 40)
    blocks = assemble_blocks(lines("Error", "follows:") + [img] + lines("Which?"), writer.writer_for(9))
    assert blocks == [TextBlock(text="Error follows:"), ImageBlock(src="images/q009_1.png", w=50, h=40), TextBlock(text="Which?")]
    assert (tmp_path / "bank" / "images" / "q009_1.png").is_file()


def test_assemble_blocks_drops_empty_text():
    assert assemble_blocks(lines("  ", ""), lambda img: None) == []


def test_image_writer_numbers_images_per_question(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    write = writer.writer_for(243)
    assert [write(image()).src for _ in range(3)] == ["images/q243_1.png", "images/q243_2.png", "images/q243_3.png"]
    assert writer.writer_for(7)(image()).src == "images/q007_1.png"
    assert writer.written == 4


def test_image_writer_converts_jpeg_to_png(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    block = writer.writer_for(1)(image(fmt="jpeg"))
    assert block.src.endswith(".png")
    assert (tmp_path / "b" / block.src).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_writer_falls_back_to_placeholder_on_bad_bytes(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    bad = Image(data=b"not an image", ext="jpeg", width=10, height=10, page=1)
    assert writer.writer_for(1)(bad) == TextBlock(text=MISSING_IMAGE_TEXT)
    assert writer.warnings and "Q1" in writer.warnings[0]


def test_reset_dir_clears_stale_images(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    writer.writer_for(1)(image())
    writer.reset_dir()
    assert writer.images_dir.is_dir() and list(writer.images_dir.iterdir()) == []


def test_build_question_resolves_key_and_select_count(tmp_path):
    raw = RawQuestion(number=10, page=1, topic="1", stem_parts=lines("Pick (Choose three)"),
                      options=[RawOption(l, lines(l.lower())) for l in "ABCDEF"],
                      pdf_answer=["B", "D", "E"], votes=[Vote(["B", "D", "E"], 90)])
    q = build_question(raw, ImageWriter(tmp_path).writer_for(10))
    assert q.number == 10 and q.topic == "1"
    assert q.answer == ["B", "D", "E"] and q.select_count == 3
    assert q.answer_source == "votes" and q.disputed is False
    assert q.pdf_answer == ["B", "D", "E"] and q.votes == [Vote(["B", "D", "E"], 90)]
    assert q.stem == [TextBlock(text="Pick (Choose three)")]
    assert [o.letter for o in q.options] == list("ABCDEF") and q.options[0].content == [TextBlock(text="a")]


def test_build_question_without_pdf_answer(tmp_path):
    raw = RawQuestion(number=1, page=1, stem_parts=lines("S"), options=[RawOption("A", lines("a"))])
    q = build_question(raw, ImageWriter(tmp_path).writer_for(1))
    assert q.answer == [] and q.select_count == 0 and q.pdf_answer == [] and q.answer_source == "pdf"
