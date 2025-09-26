import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ctf_scanner import extract_from_html, BeautifulSoup


def test_extract_with_bs4_or_fallback():
    html = '<html><body><my-widget data-info="x"></my-widget><div custom-attr="1"></div></body></html>'
    info = extract_from_html(html)
    assert isinstance(info, dict)
    assert 'tags' in info and 'attrs' in info
    # tags should include 'my-widget'
    assert any('my-widget' in t for t in info['tags'])
    # attrs should include 'custom-attr'
    assert any('custom-attr' in a for a in info['attrs'])
