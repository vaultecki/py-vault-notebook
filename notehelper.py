import asciidoc
import logging
import io
import re
import jaro
import os.path


max_file_kb=300
file_match_weight=1.5

logger = logging.getLogger(__name__)


def text_2_html(text_in):
    # print("convert asciidoc text")
    text_out = io.StringIO()
    test = asciidoc.AsciiDocAPI()
    test.execute(io.StringIO(text_in), text_out, backend="html5")
    return text_out.getvalue()

def search_files(search_text, files, project_path, cut_off=0.8):
    logger.info("semantic search")
    search_l = search_text.lower()

    results = []

    for file in files:
        file_path = os.path.join(project_path, file)

        # Skip large/binary files
        if not file.endswith((".adoc", ".asciidoc", ".txt", ".md")):
            # Filename-only relevance
            score = compute_relevance_score(search_l, file, "")
            if score > 0:
                results.append((file, score))
            continue

        try:
            if os.path.getsize(file_path) > max_file_kb * 1024:
                continue

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

            score = compute_relevance_score(search_l, file, text)

            if score > 0:
                results.append((file, score))

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")

    # Sort by descending score
    results.sort(key=lambda x: x[1], reverse=True)

    # Create result page
    result_text = f"== Results for \"{search_text}\"\n\n"

    if not results:
        return result_text + "_No results found._\n"

    result_text += "=== Ranked by relevance\n"
    for fname, score in results:
        result_text += f"* link:{fname}[{fname}] — score {score:.2f}\n"
    return result_text

def compute_relevance_score(search, filename, text):
    search_l = search.lower()
    fname = filename.lower()
    score = 0.0

    # -------------------------------
    # 1) Filename matches
    # -------------------------------
    if search_l in fname:
        score += 3.0

    # similarity-based match
    sim = jaro.jaro_winkler_metric(fname, search_l)
    if sim > 0.85:
        score += sim * 2.0

    # -------------------------------
    # 2) Headings (Asciidoc)
    # -------------------------------
    headings = re.findall(r"(?m)^(={1,6})\s+(.+)$", text)
    for level, title in headings:
        title_l = title.lower()
        if search_l in title_l:
            score += 4.0 + (1.0 / len(level))  # == wichtiger als ======

    # -------------------------------
    # 3) Emphasis or bold *text* or _text_
    # -------------------------------
    for emp in re.findall(r"[*_](.+?)[*_]", text):
        if search_l in emp.lower():
            score += 2.5

    # -------------------------------
    # 4) Link texts link:target[TEXT]
    # -------------------------------
    for link_text in re.findall(r"link:[^\[]+\[([^\]]+)\]", text):
        if search_l in link_text.lower():
            score += 2.0

    # -------------------------------
    # 5) Word-boundary matches
    # -------------------------------
    if re.search(rf"\b{re.escape(search_l)}\b", text.lower()):
        score += 2.0

    # -------------------------------
    # 6) Keyword frequency (TF-like)
    # -------------------------------
    freq = text.lower().count(search_l)
    if freq > 0:
        score += 1.0 * min(freq, 5)  # capped

    return score


if __name__ == "__main__":
    print("moin")
