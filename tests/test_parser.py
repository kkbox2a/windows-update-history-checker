from scripts.fetch_updates import (
    extract_insider_links,
    extract_msu_url,
    parse_insider_page,
    parse_update_anchor,
)


def test_title_parser():
    item = parse_update_anchor(
        "June 23, 2026—KB5095093 (OS Builds 26200.8737 and 26100.8737) Preview",
        "/example",
        "https://support.microsoft.com",
    )
    assert item is not None
    assert item.id == "KB5095093"
    assert item.kb == "KB5095093"
    assert item.builds == ["26200.8737", "26100.8737"]
    assert item.version == "25H2"
    assert item.update_type == "Preview"


def test_msu_selects_exact_kb():
    html = """
    https://catalog.sf.dl.delivery.mp.microsoft.com/files/windows11.0-kb5043080-x64_a.msu
    https://catalog.sf.dl.delivery.mp.microsoft.com/files/windows11.0-kb5121767-x64_b.msu
    """
    assert "kb5121767" in extract_msu_url(html, "KB5121767").lower()


def test_insider_index_filters_26h2_builds():
    html = """
    <a href="/en-us/windows-insider/release-notes/experimental/preview-build-26300-8553">old</a>
    <a href="/en-us/windows-insider/release-notes/experimental/preview-build-26300-8697">26H2</a>
    <a href="/en-us/windows-insider/release-notes/experimental/preview-build-26300-8772">latest</a>
    <a href="/en-us/windows-insider/release-notes/experimental-future-platforms/preview-build-29617-1000">other channel</a>
    """
    links = extract_insider_links(html)
    assert [build for build, _ in links] == ["26300.8772", "26300.8697"]


def test_insider_page_parser():
    html = """
    <html><head><title>Preview Build 26300.8772</title></head>
    <body>
      <h1>Windows 11 Insider Experimental Preview Build 26300.8772</h1>
      <p>Release date: 6 July 2026</p>
      <p>Updates are based on Windows 11, version 26H2.</p>
    </body></html>
    """
    item = parse_insider_page(
        html,
        "https://learn.microsoft.com/en-us/windows-insider/release-notes/experimental/preview-build-26300-8772",
        "26300.8772",
    )
    assert item.id == "Build 26300.8772"
    assert item.date == "July 6, 2026"
    assert item.builds == ["26300.8772"]
    assert item.version == "26H2"
    assert item.update_type == "Dev / Experimental"
    assert item.msu_status == "not_applicable"
