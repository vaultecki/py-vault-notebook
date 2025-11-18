# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Helper functions for AsciiDoc conversion and file searching.
"""
import asciidoc
import logging
import io
import re
import jaro
import os
import time
from typing import List, Tuple, Dict, Optional

# Configuration
MAX_FILE_KB = 300
FILE_MATCH_WEIGHT = 1.5
CACHE_EXPIRY_SECONDS = 300  # 5 minutes

logger = logging.getLogger(__name__)


class SearchIndex:
    """
    Cache for file contents to improve search performance.
    """

    def __init__(self, expiry_seconds: int = CACHE_EXPIRY_SECONDS):
        self.cache: Dict[str, str] = {}
        self.cache_time: Dict[str, float] = {}
        self.expiry_seconds = expiry_seconds

    def get_file_content(self, file_path: str) -> Optional[str]:
        """
        Get file content from cache or read from disk.

        Args:
            file_path: Path to the file

        Returns:
            File content as string or None if error
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return None

            mtime = os.path.getmtime(file_path)
            current_time = time.time()

            # Check cache validity
            if (file_path in self.cache and
                    file_path in self.cache_time and
                    self.cache_time[file_path] >= mtime and
                    (current_time - self.cache_time[file_path]) < self.expiry_seconds):
                return self.cache[file_path]

            # Read file
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Update cache
            self.cache[file_path] = content
            self.cache_time[file_path] = current_time

            return content

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self.cache.clear()
        self.cache_time.clear()
        logger.info("Search cache cleared")

    def remove_expired(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.cache_time.items()
            if (current_time - timestamp) >= self.expiry_seconds
        ]

        for key in expired_keys:
            self.cache.pop(key, None)
            self.cache_time.pop(key, None)

        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")


# Global search index instance
_search_index = SearchIndex()


def text_2_html(text_in: str) -> str:
    """
    Convert AsciiDoc text to HTML.

    Args:
        text_in: AsciiDoc formatted text

    Returns:
        HTML formatted text

    Raises:
        Exception: If AsciiDoc conversion fails
    """
    try:
        text_out = io.StringIO()
        asciidoc_api = asciidoc.AsciiDocAPI()
        asciidoc_api.execute(io.StringIO(text_in), text_out, backend="html5")
        return text_out.getvalue()
    except Exception as e:
        logger.error(f"AsciiDoc conversion error: {e}")
        raise


def search_files(
        search_text: str,
        files: List[str],
        project_path: str,
        cut_off: float = 0.8,
        max_results: int = 50
) -> str:
    """
    Search for text in files with semantic ranking.

    Args:
        search_text: Text to search for
        files: List of file paths to search in
        project_path: Base path of the project
        cut_off: Minimum relevance score (currently unused)
        max_results: Maximum number of results to return

    Returns:
        AsciiDoc formatted search results
    """
    logger.info(f"Semantic search for: {search_text}")
    search_l = search_text.lower()
    results: List[Tuple[str, float]] = []

    # Clean expired cache entries
    _search_index.remove_expired()

    for file in files:
        file_path = os.path.join(project_path, file)

        # Skip large/binary files - only check filename
        if not file.endswith((".adoc", ".asciidoc", ".txt", ".md")):
            score = _compute_filename_score(search_l, file)
            if score > 0:
                results.append((file, score))
            continue

        try:
            # Check file size
            if os.path.getsize(file_path) > MAX_FILE_KB * 1024:
                logger.debug(f"Skipping large file: {file}")
                score = _compute_filename_score(search_l, file)
                if score > 0:
                    results.append((file, score))
                continue

            # Get content from cache
            text = _search_index.get_file_content(file_path)
            if text is None:
                continue

            score = compute_relevance_score(search_l, file, text)

            if score > 0:
                results.append((file, score))

        except Exception as e:
            logger.error(f"Error in semantic search for {file}: {e}")

    # Sort by descending score
    results.sort(key=lambda x: x[1], reverse=True)

    # Limit results
    results = results[:max_results]

    # Create result page
    return _format_search_results(search_text, results)


def _compute_filename_score(search: str, filename: str) -> float:
    """
    Compute relevance score based only on filename.

    Args:
        search: Search term (lowercase)
        filename: Filename to check

    Returns:
        Relevance score
    """
    fname = filename.lower()
    score = 0.0

    # Exact substring match
    if search in fname:
        score += 3.0 * FILE_MATCH_WEIGHT

    # Similarity-based match
    sim = jaro.jaro_winkler_metric(fname, search)
    if sim > 0.85:
        score += sim * 2.0 * FILE_MATCH_WEIGHT

    return score


def compute_relevance_score(search: str, filename: str, text: str) -> float:
    """
    Compute relevance score for a file based on search term.

    Args:
        search: Search term (lowercase)
        filename: Filename
        text: File content

    Returns:
        Relevance score (higher is better)
    """
    fname = filename.lower()
    score = 0.0

    # -------------------------------
    # 1) Filename matches
    # -------------------------------
    score += _compute_filename_score(search, filename)

    # -------------------------------
    # 2) Headings (AsciiDoc)
    # -------------------------------
    headings = re.findall(r"(?m)^(={1,6})\s+(.+)$", text)
    for level, title in headings:
        title_l = title.lower()
        if search in title_l:
            # Higher level headings (fewer =) are more important
            score += 4.0 + (1.0 / len(level))

    # -------------------------------
    # 3) Emphasis or bold *text* or _text_
    # -------------------------------
    for emp in re.findall(r"[*_](.+?)[*_]", text):
        if search in emp.lower():
            score += 2.5

    # -------------------------------
    # 4) Link texts link:target[TEXT]
    # -------------------------------
    for link_text in re.findall(r"link:[^\[]+\[([^\]]+)\]", text):
        if search in link_text.lower():
            score += 2.0

    # -------------------------------
    # 5) Word-boundary matches (whole word)
    # -------------------------------
    if re.search(rf"\b{re.escape(search)}\b", text.lower()):
        score += 2.0

    # -------------------------------
    # 6) Keyword frequency (TF-like)
    # -------------------------------
    freq = text.lower().count(search)
    if freq > 0:
        # Cap at 5 to prevent single-word spam
        score += 1.0 * min(freq, 5)

    return score


def _format_search_results(search_text: str, results: List[Tuple[str, float]]) -> str:
    """
    Format search results as AsciiDoc.

    Args:
        search_text: Original search query
        results: List of (filename, score) tuples

    Returns:
        AsciiDoc formatted results
    """
    result_text = f"== Results for \"{search_text}\"\n\n"

    if not results:
        return result_text + "_No results found._\n"

    result_text += f"=== Found {len(results)} results (ranked by relevance)\n\n"

    for fname, score in results:
        result_text += f"* link:{fname}[{fname}] — score {score:.2f}\n"

    return result_text


def clear_search_cache() -> None:
    """Clear the search cache. Useful when files have been modified externally."""
    _search_index.clear_cache()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Testing notehelper...")

    # Test text conversion
    test_text = "== Test Heading\n\nSome *bold* text."
    try:
        html = text_2_html(test_text)
        print("HTML conversion successful")
        print(html[:100])
    except Exception as e:
        print(f"Error: {e}")

    # Test search
    test_files = ["test.adoc", "readme.md", "notes.txt"]
    results = search_files("test", test_files, ".", cut_off=0.5)
    print("\nSearch results:")
    print(results)
