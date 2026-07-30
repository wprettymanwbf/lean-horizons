from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import mammoth
from markdownify import markdownify as html_to_markdown
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "originals" / "metadata" / "documents-manifest.json"

HTML_STYLE = """
body {
  margin: 0;
  font-family: Georgia, 'Times New Roman', serif;
  background: #f6f1e8;
  color: #1f1a17;
}
main {
  max-width: 52rem;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
h1, h2, h3 {
  line-height: 1.2;
}
.meta {
  color: #5a4d45;
  font-size: 0.95rem;
  margin-bottom: 1.5rem;
}
.content p, .content li {
  font-size: 1.05rem;
  line-height: 1.65;
}
.content table {
  width: 100%;
  border-collapse: collapse;
  overflow-x: auto;
  display: block;
}
.content th, .content td {
  border: 1px solid #c9b8a8;
  padding: 0.6rem;
  text-align: left;
  vertical-align: top;
}
a {
  color: #0a5c63;
}
@media (min-width: 720px) {
  main {
    padding: 2.5rem 2rem 4rem;
  }
}
""".strip()


def slugify(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def comparable_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def normalize_pdf_text(text: str) -> list[str]:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)

    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [re.sub(r"\s+", " ", line).strip() for line in block.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue
        paragraph = " ".join(lines)
        paragraph = re.sub(r"\s+", " ", paragraph).strip()
        if paragraph:
            paragraphs.append(paragraph)

    return paragraphs


def extract_pdf_content(source_path: Path) -> tuple[str, list[str]]:
    reader = PdfReader(str(source_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    paragraphs = normalize_pdf_text("\n\n".join(pages))
    title = paragraphs[0] if paragraphs else source_path.stem
    return title, paragraphs


def extract_docx_content(source_path: Path) -> tuple[str, str, str]:
    with source_path.open("rb") as handle:
        result = mammoth.convert_to_html(handle)
    html_body = result.value.strip()
    markdown_body = html_to_markdown(html_body, heading_style="ATX")
    title_match = re.search(r"<p><strong><em>(.*?)</em></strong></p>", html_body)
    title = title_match.group(1).strip() if title_match else source_path.stem
    return title, markdown_body.strip(), html_body


def build_markdown(title: str, entry: dict, body: str) -> str:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    frontmatter = [
        "---",
        f'title: "{title.replace("\"", "\\\"")}"',
        f'id: "{entry["id"]}"',
        f'section: "{entry["section"]}"',
        f'source_path: "{entry["source_path"]}"',
        f'source_format: "{entry["source_format"]}"',
        f'generated_at: "{generated_at}"',
        "---",
        "",
    ]
    return "\n".join(frontmatter) + body.strip() + "\n"


def build_pdf_markdown(title: str, entry: dict, paragraphs: list[str]) -> str:
    body_paragraphs = paragraphs
    if paragraphs and comparable_text(paragraphs[0]).startswith(comparable_text(title)):
        body_paragraphs = paragraphs[1:]

    body_lines = [f"# {title}", ""]
    for paragraph in body_paragraphs:
        body_lines.append(paragraph)
        body_lines.append("")
    if len(body_lines) == 2:
        body_lines.append("No extractable text was found in the source PDF.")
        body_lines.append("")
    return build_markdown(title, entry, "\n".join(body_lines).strip())


def build_html_document(title: str, entry: dict, body_html: str) -> str:
    source_path = html.escape(entry["source_path"])
    source_format = html.escape(entry["source_format"].upper())
    section = html.escape(entry["section"])
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{escaped_title}</title>
    <style>{HTML_STYLE}</style>
  </head>
  <body>
    <main>
      <h1>{escaped_title}</h1>
      <p class=\"meta\">Section: {section} | Source: {source_format} | Original: {source_path}</p>
      <article class=\"content\">
        {body_html}
      </article>
    </main>
  </body>
</html>
"""


def build_pdf_html(title: str, entry: dict, paragraphs: list[str]) -> str:
    body_paragraphs = paragraphs
    if paragraphs and comparable_text(paragraphs[0]).startswith(comparable_text(title)):
        body_paragraphs = paragraphs[1:]

    html_paragraphs = [f"<p>{html.escape(paragraph)}</p>" for paragraph in body_paragraphs]
    if not html_paragraphs:
        html_paragraphs = ["<p>No extractable text was found in the source PDF.</p>"]
    return build_html_document(title, entry, "\n        ".join(html_paragraphs))


def write_section_indexes(section: str, entries: list[dict]) -> None:
    markdown_dir = ROOT / "processed" / "markdown" / section
    html_dir = ROOT / "processed" / "html" / section
    markdown_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)

    markdown_lines = [f"# {section.replace('-', ' ').title()}", "", "Converted documents:", ""]
    html_items: list[str] = []
    for entry in entries:
        md_target = Path(entry["targets"][0])
        html_target = Path(entry["targets"][1])
        markdown_lines.append(f"- [{entry['title']}]({md_target.name})")
        html_items.append(f"<li><a href=\"{html.escape(html_target.name)}\">{html.escape(entry['title'])}</a></li>")

    (markdown_dir / "index.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    html_index = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>{html.escape(section)}</title>
    <style>{HTML_STYLE}</style>
  </head>
  <body>
    <main>
      <h1>{html.escape(section.replace('-', ' ').title())}</h1>
      <ul>
        {''.join(html_items)}
      </ul>
    </main>
  </body>
</html>
"""
    (html_dir / "index.html").write_text(html_index, encoding="utf-8")


def write_root_indexes(section_map: dict[str, list[dict]]) -> None:
    markdown_root = ROOT / "processed" / "markdown"
    html_root = ROOT / "processed" / "html"
    markdown_root.mkdir(parents=True, exist_ok=True)
    html_root.mkdir(parents=True, exist_ok=True)

    markdown_lines = ["# Processed Markdown", "", "This directory contains the canonical AI-readable versions of source documents.", ""]
    html_items: list[str] = []
    for section in sorted(section_map):
        markdown_lines.append(f"- [{section.replace('-', ' ').title()}]({section}/index.md)")
        html_items.append(f"<li><a href=\"{html.escape(section)}/index.html\">{html.escape(section.replace('-', ' ').title())}</a></li>")

    (markdown_root / "index.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    html_index = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Lean Horizons Processed HTML</title>
    <style>{HTML_STYLE}</style>
  </head>
  <body>
    <main>
      <h1>Processed HTML</h1>
      <ul>
        {''.join(html_items)}
      </ul>
    </main>
  </body>
</html>
"""
    (html_root / "index.html").write_text(html_index, encoding="utf-8")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def process_manifest() -> None:
    manifest = load_manifest()
    section_map: dict[str, list[dict]] = defaultdict(list)

    for entry in manifest["documents"]:
        source_path = ROOT / entry["source_path"]
        markdown_target = ROOT / entry["targets"][0]
        html_target = ROOT / entry["targets"][1]
        ensure_parent(markdown_target)
        ensure_parent(html_target)

        if entry["source_format"].lower() == "pdf":
          extracted_title, paragraphs = extract_pdf_content(source_path)
          title = entry.get("title") or extracted_title
          markdown_text = build_pdf_markdown(title, entry, paragraphs)
          html_text = build_pdf_html(title, entry, paragraphs)
        elif entry["source_format"].lower() == "docx":
            extracted_title, markdown_body, html_body = extract_docx_content(source_path)
            title = entry.get("title") or extracted_title
            markdown_text = build_markdown(title, entry, markdown_body)
            html_text = build_html_document(title, entry, html_body)
        else:
            raise ValueError(f"Unsupported source format: {entry['source_format']}")

        markdown_target.write_text(markdown_text, encoding="utf-8")
        html_target.write_text(html_text, encoding="utf-8")

        entry["title"] = title
        entry["status"] = "converted"
        entry["converted_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        section_map[entry["section"]].append(entry)

    for section, entries in section_map.items():
        write_section_indexes(section, entries)
    write_root_indexes(section_map)
    write_manifest(manifest)


if __name__ == "__main__":
    process_manifest()