#!/usr/bin/env python3
"""
translate.py - Fetch, translate, and format Project Euler problems for PE-CN.

Usage:
    python scripts/translate.py 969
    python scripts/translate.py 969 970 971
    python scripts/translate.py --catchup
"""

import os
import re
import sys
import time
import random
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import anthropic

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
POSTS_DIR = ROOT / "source" / "_posts"
IMAGES_DIR = ROOT / "source" / "resources" / "images"
RULES_FILE = POSTS_DIR / "rules.txt"
ENV_FILE = ROOT / ".env"

PE_BASE = "https://projecteuler.net"

# ---------------------------------------------------------------------------
# Config / credentials
# ---------------------------------------------------------------------------

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PE-CN-translator/1.0"})


def get(url, **kwargs):
    resp = SESSION.get(url, timeout=15, **kwargs)
    resp.raise_for_status()
    return resp


def polite_sleep():
    time.sleep(random.uniform(2.0, 4.0))

# ---------------------------------------------------------------------------
# Step 1: find latest problem and missing problems
# ---------------------------------------------------------------------------

def get_latest_problem_number() -> int:
    resp = get(f"{PE_BASE}/recent")
    soup = BeautifulSoup(resp.text, "html.parser")
    numbers = []
    for tr in soup.select("table tr"):
        tds = tr.find_all("td")
        if tds:
            try:
                numbers.append(int(tds[0].get_text(strip=True)))
            except ValueError:
                pass
    if not numbers:
        raise RuntimeError("Could not parse problem numbers from /recent")
    return max(numbers)


def get_missing_problems() -> list[int]:
    existing = {int(f.stem) for f in POSTS_DIR.glob("*.md") if f.stem.isdigit()}
    latest = get_latest_problem_number()
    print(f"Latest problem on PE: {latest}")
    missing = sorted(n for n in range(1, latest + 1) if n not in existing)
    print(f"Missing {len(missing)} problems: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    return missing

# ---------------------------------------------------------------------------
# Step 2: fetch title and date from problem=N
# ---------------------------------------------------------------------------

def parse_date(raw: str) -> str:
    """'Sunday, 9th November 2025, 01:00 am' → '2025/11/09 01:00:00'"""
    raw = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", raw)
    raw = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", raw.strip())
    for fmt in ("%d %B %Y, %I:%M %p", "%d %B %Y, %I:%M%p"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y/%m/%d %H:%M:%S")
        except ValueError:
            continue
    # Fallback: today
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def fetch_title_and_date(n: int) -> tuple[str, str]:
    resp = get(f"{PE_BASE}/problem={n}")
    soup = BeautifulSoup(resp.text, "html.parser")

    # Title is the <h2> inside the problem content
    h2 = soup.find("h2")
    title = h2.get_text(strip=True) if h2 else f"Problem {n}"

    # Date: "Published on <date_string>"
    date_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    text = soup.get_text(" ")
    m = re.search(r"Published on\s+(.+?);", text)
    if m:
        date_str = parse_date(m.group(1))

    return title, date_str

# ---------------------------------------------------------------------------
# Step 3: fetch and parse minimal=N → clean markdown
# ---------------------------------------------------------------------------

def download_image(img_url: str) -> str:
    """Download an image from PE and save to source/resources/images/.
    Returns the local web path e.g. '/resources/images/0962_foo.png'."""
    # Strip query string from filename (e.g. '0972_foo.png?1762877126' → '0972_foo.png')
    filename = Path(urlparse(img_url).path).name
    local_path = IMAGES_DIR / filename
    if not local_path.exists():
        resp = get(img_url)
        local_path.write_bytes(resp.content)
        print(f"  Downloaded image: {filename}")
        polite_sleep()
    return f"/resources/images/{filename}"


def escape_math(text: str) -> str:
    """Escape LaTeX sequences that conflict with Hexo/Marked/MathJax.

    The Hexo markdown renderer processes backslash escapes before MathJax
    sees the content, so:
      \\   (LaTeX line-break)    →  \\\\
      \\{  (literal left-brace)  →  \\\\{   (i.e. \\\\\\{ in the file = \\{ for MathJax)
      \\}  (literal right-brace) →  \\\\}
      \\$  (literal dollar)      →  \\\\$
    Also: \\, (thin space used on PE) → \\ (regular space), unsupported by MathJax.
    """
    BS = "\\"
    # \, must come before \\ → \\\\ so we don't create a spurious \, after doubling
    text = text.replace(BS + ",", BS + " ")    # \, (thin space) → \  (space)
    # Order matters: do \\ first so we don't double-escape later substitutions
    text = text.replace(BS * 2, BS * 4)   # \\ → \\\\
    text = text.replace(BS + "{", BS * 3 + "{")   # \{ → \\\{
    text = text.replace(BS + "}", BS * 3 + "}")   # \} → \\\}
    text = text.replace(BS + "$", BS * 3 + "$")   # \$ → \\\$
    return text


def apply_math_escaping(text: str) -> str:
    """Apply escape_math only inside $...$ and $$...$$ regions."""
    # Split text into math and non-math segments.
    # We handle $$...$$ before $...$ to avoid mis-matching.
    parts = []
    pattern = re.compile(r"(\$\$[\s\S]*?\$\$|\$(?!\$)[^\$\n]*?\$)", re.DOTALL)
    last = 0
    for m in pattern.finditer(text):
        parts.append(text[last:m.start()])  # non-math: unchanged
        parts.append(escape_math(m.group()))  # math: escaped
        last = m.end()
    parts.append(text[last:])
    return "".join(parts)


def node_to_md(node, inside_list=False) -> str:
    """Recursively convert a BeautifulSoup node to markdown text."""
    if isinstance(node, NavigableString):
        text = str(node)
        # Strip leading newline if previous sibling is <br> (it's HTML indentation, not content)
        prev = node.previous_sibling
        if prev and getattr(prev, "name", None) == "br":
            text = text.lstrip("\n")
        return text

    tag = node.name
    if tag is None:
        return ""

    children_md = lambda: "".join(node_to_md(c) for c in node.children)

    if tag == "p":
        inner = children_md().strip()
        # Remove a trailing <br> that's at the very end of a paragraph
        inner = re.sub(r"<br\s*/?>\s*$", "", inner).rstrip()
        return inner + "\n\n"

    elif tag in ("ul", "ol"):
        items = []
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            inner = "".join(node_to_md(c) for c in li.children).strip()
            prefix = f"{i}. " if tag == "ol" else "- "
            items.append(prefix + inner)
        return "\n".join(items) + "\n\n"

    elif tag == "li":
        # Handled above inside ul/ol; fallback if encountered standalone
        return "- " + children_md().strip() + "\n"

    elif tag == "br":
        return "<br>\n"

    elif tag in ("b", "strong"):
        return f"**{children_md()}**"

    elif tag == "i":
        return f"<i>{children_md()}</i>"

    elif tag in ("em",):
        return f"*{children_md()}*"

    elif tag == "var":
        return f"${children_md()}$"

    elif tag == "sup":
        inner = children_md()
        # Only wrap in LaTeX if not already in a math context
        return f"^{{{inner}}}"

    elif tag == "sub":
        inner = children_md()
        return f"_{{{inner}}}"

    elif tag == "a":
        href = node.get("href", "")
        inner = children_md()
        if href:
            # Absolutify relative URLs
            if not href.startswith("http"):
                href = urljoin(PE_BASE + "/", href.lstrip("/"))
            # If the link points to an image file, download it locally
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            if Path(urlparse(href).path).suffix.lower() in IMAGE_EXTS:
                href = download_image(href)
            return f"[{inner}]({href})"
        return inner

    elif tag == "img":
        src = node.get("src", "")
        alt = node.get("alt", "")
        if src:
            if not src.startswith("http"):
                src = urljoin(PE_BASE + "/", src.lstrip("/"))
            local_path = download_image(src)
            filename = Path(local_path).name
            # Check if parent is already a centering div; if so, just return the <img> tag
            parent = node.parent
            parent_is_center = (
                parent is not None
                and getattr(parent, "name", None) == "div"
                and (
                    "center" in (parent.get("style") or "")
                    or (parent.get("align") or "").strip().lower() == "center"
                )
            )
            img_tag = f'<img src="{local_path}" alt="{filename}">'
            if parent_is_center:
                return img_tag
            return f'<div style="text-align:center">{img_tag}</div>\n\n'
        return ""

    elif tag == "div":
        inner = children_md()
        style = node.get("style", "") or ""
        align = node.get("align", "") or ""
        if "center" in style or align.strip().lower() == "center":
            inner = inner.strip()
            return f'<div style="text-align:center">{inner}</div>\n\n'
        return inner

    elif tag == "table":
        return convert_table(node)

    elif tag in ("h1", "h2", "h3"):
        level = int(tag[1])
        return "#" * level + " " + children_md().strip() + "\n\n"

    elif tag == "blockquote":
        lines = children_md().strip().splitlines()
        return "\n".join("> " + l for l in lines) + "\n\n"

    elif tag in ("span", "td", "th", "tr", "tbody", "thead"):
        return children_md()

    else:
        return children_md()


def convert_table(table_node) -> str:
    """Convert an HTML <table> to a GitHub-Flavored Markdown table."""
    rows = []
    for tr in table_node.find_all("tr"):
        cells = []
        for cell in tr.find_all(["th", "td"]):
            # Check alignment from style/align attribute
            align = cell.get("align", "") or ""
            style = cell.get("style", "") or ""
            if "center" in align or "center" in style:
                cell_align = ":---:"
            elif "right" in align or "right" in style:
                cell_align = "---:"
            else:
                cell_align = ":---"
            text = "".join(node_to_md(c) for c in cell.children).strip()
            cells.append((text, cell_align, cell.name == "th"))
        if cells:
            rows.append(cells)

    if not rows:
        return ""

    # Figure out alignment row from first data row or header
    num_cols = max(len(r) for r in rows)
    # Pad rows to same width
    for r in rows:
        while len(r) < num_cols:
            r.append(("", ":---", False))

    lines = []
    # If first row has <th>, use it as header
    first_row = rows[0]
    is_header = any(cell[2] for cell in first_row)

    header_cells = [cell[0] for cell in first_row]
    lines.append("| " + " | ".join(header_cells) + " |")

    # Separator row
    sep_cells = [cell[1] for cell in first_row]
    lines.append("| " + " | ".join(sep_cells) + " |")

    # Data rows
    start = 1 if is_header else 1
    for row in rows[start:]:
        data_cells = [cell[0] for cell in row]
        lines.append("| " + " | ".join(data_cells) + " |")

    return "\n".join(lines) + "\n\n"


def fetch_body_md(n: int) -> str:
    """Fetch minimal=N, convert HTML body to markdown, apply math escaping."""
    resp = get(f"{PE_BASE}/minimal={n}")
    soup = BeautifulSoup(resp.text, "html.parser")

    # The minimal endpoint returns just the problem body HTML (no <html>/<body> wrapper)
    # Parse all top-level nodes
    md_parts = []
    for node in soup.children:
        md_parts.append(node_to_md(node))

    raw_md = "".join(md_parts).strip()

    # Post-process: <br> immediately before a blank line is dangling — strip it, keep the blank line
    raw_md = re.sub(r"<br\s*/?>\n\n", "\n\n", raw_md)
    # Collapse 3+ consecutive newlines to 2 (one blank line)
    raw_md = re.sub(r"\n{3,}", "\n\n", raw_md)

    escaped = apply_math_escaping(raw_md)
    return escaped

# ---------------------------------------------------------------------------
# Step 4: translate with Claude
# ---------------------------------------------------------------------------

def load_rules() -> str:
    if RULES_FILE.exists():
        return RULES_FILE.read_text(encoding="utf-8")
    return ""


SYSTEM_PROMPT = """\
You are translating Project Euler problems from English to Chinese for a bilingual translation website (PE-CN).

## Style guide
{rules}

## Formatting rules (MUST follow exactly)
- Preserve ALL LaTeX math expressions verbatim — do not modify any math, including escape sequences like \\\\, \\\\{{, \\\\}}, \\\\$.
- Preserve ALL HTML tags verbatim: <br>, <br/>, <div style="text-align:center">, <img ...>, etc.
- Preserve ALL markdown formatting: **bold**, *italic*, tables (pipe syntax), bullet lists (- ), numbered lists (1. ).
- The English body may contain `<i>...</i>` (italic) tags. In your Chinese translation, replace each `<i>...</i>` with `<i class=zh>...</i>` (translating the inner text). Do NOT use `<i class=zh>` for any other purpose — text in **bold** (`**...**`) or any other format stays in its original format.
- Convert English number words to Arabic numerals (e.g. "twenty-one" → "21", "one-hundred" → "100").
- ALL English names and proper nouns MUST be rendered in Chinese — do NOT leave any name in English. Use standard Chinese transliterations for mathematicians and historical figures (e.g. Euler → 欧拉, Fibonacci → 斐波那契, Pascal → 帕斯卡, Gauss → 高斯, Newton → 牛顿, Bernoulli → 伯努利, Leibniz → 莱布尼茨). For less common names, provide a reasonable phonetic transliteration.
- For internal Project Euler links like [Problem N](https://projecteuler.net/problem=N), change to [第N题](/N).
- "Give your answer modulo X" → "并对X取余作为你的答案"
- "You are given" → "已知"
- "Find" at the start of a question → "求"
- "let" (when introducing a mathematical variable or definition) → "记" (not "设")
- Do not add spaces between text and inline math delimiters: write "满足$n<100$的" not "满足 $n<100$ 的".
- Do not insert a blank line before a list (ordered or unordered); the list should immediately follow the preceding line with only a single newline.
- Do NOT add any extra text, explanation, or commentary.

## Output format
Return EXACTLY two sections separated by a blank line:
1. First line: the Chinese title only (no label, no punctuation prefix)
2. Blank line
3. The rest: Chinese translation of the body, preserving all formatting exactly as described above.
"""


def post_process_zh(text: str) -> str:
    """Clean up common Claude formatting artifacts in Chinese translation."""
    # Remove spaces adjacent to inline math delimiters (single $, not display $$)
    text = re.sub(r' (\$(?!\$))', r'\1', text)           # space before opening $
    text = re.sub(r'((?<!\$)\$(?!\$)) ', r'\1', text)    # space after closing $
    # Remove blank lines immediately before list items
    text = re.sub(r'\n\n(- |\* |\d+\. )', r'\n\1', text)
    # Replace \, (thin space) with \  inside math regions (safety net for Claude-generated math)
    def _fix_thin_space(m):
        return m.group().replace("\\,", "\\ ")
    text = re.sub(r"\$\$[\s\S]*?\$\$|\$(?!\$)[^\$\n]*?\$", _fix_thin_space, text, flags=re.DOTALL)
    return text


def translate(n: int, en_title: str, en_body: str) -> tuple[str, str]:
    """Call Claude to produce (zh_title, zh_body)."""
    rules = load_rules()
    system = SYSTEM_PROMPT.format(rules=rules)

    client = anthropic.Anthropic(api_key=API_KEY)

    user_msg = f"English title: {en_title}\n\nEnglish body:\n{en_body}"

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    response = message.content[0].text.strip()

    # Split into title (first line) and body (rest)
    lines = response.split("\n", 1)
    zh_title = lines[0].strip()
    zh_body = lines[1].strip() if len(lines) > 1 else ""

    zh_body = post_process_zh(zh_body)
    return zh_title, zh_body

# ---------------------------------------------------------------------------
# Step 5: write the post file
# ---------------------------------------------------------------------------

def write_post(n: int, date: str, en_title: str, en_body: str, zh_title: str, zh_body: str):
    out = POSTS_DIR / f"{n}.md"
    en_body = en_body.strip()
    zh_body = zh_body.strip()
    content = (
        f"title: Problem {n}\n"
        f"date: {date}\n"
        f"---\n"
        f"\n"
        f"***\n"
        f"# [Problem {n}](https://projecteuler.net/problem={n})\n"
        f"***\n"
        f"## **{en_title}**\n"
        f"\n"
        f"{en_body}\n"
        f"\n"
        f"***\n"
        f"## **{zh_title}**\n"
        f"\n"
        f"{zh_body}\n"
        f"\n"
        f"***\n"
    )
    out.write_text(content, encoding="utf-8")
    print(f"  Written: {out}")

# ---------------------------------------------------------------------------
# Step 6: update the problem index page
# ---------------------------------------------------------------------------

INDEX_PATH = ROOT / "source" / "problems" / "index.md"


def update_index():
    """Rebuild the problem index table in source/problems/index.md.

    Columns are always grouped by centuries (1-100, 101-200, …).
    The last column header says "NNN <br> ~ now"; completed centuries
    show their full range, e.g. "901 <br> ~ 1000".
    New columns are added automatically when problems cross a century
    boundary (e.g., when problem 1001 appears).
    """
    problems = sorted(int(f.stem) for f in POSTS_DIR.glob("*.md") if f.stem.isdigit())
    if not problems:
        return

    problem_set = set(problems)
    max_n = max(problems)
    num_cols = (max_n - 1) // 100 + 1  # number of century columns needed

    # --- Build column headers ---
    headers = []
    for c in range(num_cols):
        start = c * 100 + 1
        end = (c + 1) * 100
        if c == num_cols - 1:
            headers.append(f"{start:03d} <br> ~ now")
        else:
            headers.append(f"{start:03d} <br> ~ {end}")

    # --- Build table rows (always 100 rows to cover a full century) ---
    sep = " | ".join([":-:"] * num_cols)
    header_row = " | ".join(headers)

    data_rows = []
    for row in range(100):  # offset 0–99 within each century
        cells = []
        for col in range(num_cols):
            n = col * 100 + row + 1
            cells.append(f"[{n:03d}](/{n})" if n in problem_set else "")
        data_rows.append(" | ".join(cells))

    table_md = header_row + "\n" + sep + "\n" + "\n".join(data_rows)

    # --- Splice into the index file ---
    content = INDEX_PATH.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # Locate the existing table: find the line containing "001 <br>"
    # and the closing "***" that follows it.
    table_start = next(
        (i for i, l in enumerate(lines) if "001 <br>" in l), None
    )
    if table_start is None:
        print("  Warning: could not locate table in index.md — skipping index update")
        return

    table_end = next(
        (i for i in range(table_start + 1, len(lines)) if lines[i].strip() == "***"),
        None,
    )
    if table_end is None:
        print("  Warning: could not find closing *** after table — skipping index update")
        return

    new_lines = lines[:table_start] + [table_md + "\n\n"] + lines[table_end:]
    INDEX_PATH.write_text("".join(new_lines), encoding="utf-8")
    print(f"  Updated index: {len(problems)} problems, {num_cols} column(s)")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def bump_date(date: str, seconds: int = 1) -> str:
    from datetime import timedelta
    dt = datetime.strptime(date, "%Y/%m/%d %H:%M:%S") + timedelta(seconds=seconds)
    return dt.strftime("%Y/%m/%d %H:%M:%S")


def process_problem(n: int, prev_date: str | None = None) -> str:
    print(f"\n[Problem {n}]")

    # 1. Title + date (from full problem page)
    print(f"  Fetching title/date from problem={n}...")
    en_title, date = fetch_title_and_date(n)
    if prev_date and date == prev_date:
        date = bump_date(date)
        print(f"  Same publish time as previous — bumped date to {date}")
    print(f"  Title: {en_title}  Date: {date}")
    polite_sleep()

    # 2. Body (from minimal page)
    print(f"  Fetching body from minimal={n}...")
    en_body = fetch_body_md(n)
    polite_sleep()

    # 3. Translate
    print(f"  Translating with Claude...")
    zh_title, zh_body = translate(n, en_title, en_body)

    # 4. Write post
    write_post(n, date, en_title, en_body, zh_title, zh_body)
    return date


def main():
    parser = argparse.ArgumentParser(description="Translate Project Euler problems to Chinese.")
    parser.add_argument("problems", nargs="*", type=int, help="Problem number(s) to translate")
    parser.add_argument("--catchup", action="store_true", help="Translate all problems missing from _posts/")
    args = parser.parse_args()

    if not API_KEY:
        print("Error: ANTHROPIC_API_KEY not set. Check your .env file.", file=sys.stderr)
        sys.exit(1)

    if args.catchup:
        problems = get_missing_problems()
    elif args.problems:
        problems = args.problems
    else:
        parser.print_help()
        sys.exit(1)

    if not problems:
        print("Nothing to do.")
        return

    print(f"Processing {len(problems)} problem(s): {problems}")

    prev_date = None
    for i, n in enumerate(problems):
        try:
            prev_date = process_problem(n, prev_date)
        except Exception as e:
            print(f"  ERROR on problem {n}: {e}", file=sys.stderr)
            continue
        # Extra sleep between problems (not just between sub-requests)
        if i < len(problems) - 1:
            time.sleep(random.uniform(1.0, 2.0))

    # Update the index page once after all problems are written
    print("\nUpdating index...")
    update_index()

    print("\nDone.")


if __name__ == "__main__":
    main()
