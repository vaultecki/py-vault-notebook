import asciidoc
import logging
import io
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
    search_text_lower = search_text.lower()
    results = []

    for file in files:
        file_score = 0.0

        # 1) FILE NAME MATCH
        name_lower = file.lower()
        if search_text_lower in name_lower:
            file_score += 1.0

        # 2) SIMILARITY OF FILE NAME
        sim = jaro.jaro_winkler_metric(name_lower, search_text_lower)
        if sim > 0.85:
            file_score += sim * file_match_weight

        # Skip if no filename relevance
        if file_score == 0:
            # We still check contents below
            pass

        # 3) CONTENT MATCH / only for small text files
        file_path = os.path.join(project_path, file)

        # skip binary or large files
        if not file.endswith((".adoc", ".asciidoc", ".txt", ".md")):
            # only filenames count for non-text files
            if file_score > 0:
                results.append((file, file_score))
            continue

        try:
            if os.path.getsize(file_path) > max_file_kb * 1024:
                continue  # skip large file

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().lower()

            if search_text_lower in text:
                file_score += 2.0  # strong match

        except Exception as e:
            logger.error(f"Error reading file {file}: {e}")
            continue

        if file_score > 0:
            results.append((file, file_score))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    # Create result Asciidoc
    result_text = f"== Search results for \"{search_text}\"\n\n"

    if not results:
        return result_text + "_No results found._\n"

    result_text += "=== Results (ranked)\n"
    for filename, score in results:
        result_text += f"* link:{filename}[{filename}] — score {score:.2f}\n"
    return result_text


if __name__ == "__main__":
    print("moin")
