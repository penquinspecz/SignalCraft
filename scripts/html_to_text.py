# scripts/html_to_text.py
def html_to_text(html: str) -> str:
    # minimal dependency-free stripper (good enough)
    import re
    if not html:
        return ""
    # keep paragraph-ish separation
    html = re.sub(r"</(p|li|h\d|br)\s*>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)          # remove tags
    html = html.replace("&nbsp;", " ")
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # normalize whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    html = re.sub(r"[ \t]{2,}", " ", html)
    return html.strip()
