from exam_sim.parser.extract import Image, Line, filter_items, to_png
from tests.parser.helpers import image, image_bytes, lines


def test_filter_drops_footer_lines_and_preamble():
    items = lines("Professional Data Engineer Questions", "[202610]", "Question #1", "Topic 1",
                  "Stem", "https://zhangxuetu.online", "A. x")
    out = filter_items(items, page_count=1)
    assert [i.text for i in out] == ["Question #1", "Topic 1", "Stem", "A. x"]


def test_filter_drops_watermark_present_on_most_pages_but_keeps_content_images():
    wm = image_bytes(30, 30)
    items: list = [Line("Question #1", 1)]
    for p in range(1, 11):
        items.append(Image(data=wm, ext="png", width=30, height=30, page=p))
    content = image(50, 50, page=3)
    items.append(content)
    imgs = [i for i in filter_items(items, page_count=10) if isinstance(i, Image)]
    assert imgs == [content]


def test_filter_keeps_repeated_image_when_pdf_is_short():
    data = image_bytes(30, 30)
    items = [Line("Question #1", 1), Image(data, "png", 30, 30, 1), Image(data, "png", 30, 30, 2)]
    assert len([i for i in filter_items(items, page_count=2) if isinstance(i, Image)]) == 2


def test_filter_drops_tiny_images():
    items = [Line("Question #1", 1), image(9, 6), image(40, 40)]
    imgs = [i for i in filter_items(items, page_count=1) if isinstance(i, Image)]
    assert len(imgs) == 1 and imgs[0].width == 40


def test_to_png_passthrough_and_conversion():
    png = image_bytes(20, 10, "png")
    assert to_png(png, "png") is png
    jpg = image_bytes(20, 10, "jpeg")
    assert to_png(jpg, "jpeg")[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_digest_is_stable_per_content():
    a, b = image(20, 20), image(20, 20)
    assert a.digest == b.digest
    assert a.digest != image(21, 20).digest
