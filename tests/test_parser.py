from scripts.fetch_updates import extract_msu_url, parse_update_anchor


def test_title_parser():
    item = parse_update_anchor(
        "June 23, 2026—KB5095093 (OS Builds 26200.8737 and 26100.8737) Preview",
        "/example",
        "https://support.microsoft.com",
    )
    assert item is not None
    assert item.kb == "KB5095093"
    assert item.builds == ["26200.8737", "26100.8737"]
    assert item.update_type == "Preview"


def test_msu_selects_exact_kb():
    html = """
    https://catalog.sf.dl.delivery.mp.microsoft.com/files/windows11.0-kb5043080-x64_a.msu
    https://catalog.sf.dl.delivery.mp.microsoft.com/files/windows11.0-kb5121767-x64_b.msu
    """
    assert "kb5121767" in extract_msu_url(html, "KB5121767").lower()
