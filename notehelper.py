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


def analyze_wiki_structure(files: List[str], project_path: str) -> Dict[str, any]:
    """
    Analyze wiki structure to find orphaned files and wanted files.
    
    Args:
        files: List of file paths in the project
        project_path: Base path of the project
        
    Returns:
        Dictionary with 'orphaned' and 'wanted' file lists
    """
    logger.info("Analyzing wiki structure...")
    
    # Filter for AsciiDoc files to scan for links
    adoc_files = [f for f in files if f.endswith(('.adoc', '.asciidoc'))]
    
    # All files that could be referenced
    all_files = [f.replace(os.path.sep, '/') for f in files]
    
    # Track all links found
    all_links: Dict[str, List[str]] = {}  # target -> [source files]
    
    # Analyze each AsciiDoc file for links
    for file in adoc_files:
        file_path = os.path.join(project_path, file)
        
        try:
            content = _search_index.get_file_content(file_path)
            if not content:
                continue
            
            # Find all AsciiDoc links: link:target[text]
            link_matches = re.findall(r'link:([^\[]+)\[', content)
            
            # Find all image references: image:target[] or image::target[]
            image_matches = re.findall(r'image::?([^\[]+)\[', content)
            
            # Combine all references
            all_matches = link_matches + image_matches
            
            for link in all_matches:
                # Normalize the link path
                link = link.strip()
                
                # Skip external links
                if link.startswith(('http://', 'https://', 'ftp://', 'mailto:')):
                    continue
                
                # Calculate absolute path from current file
                current_dir = os.path.dirname(file)
                if current_dir:
                    target_path = os.path.normpath(os.path.join(current_dir, link))
                else:
                    target_path = os.path.normpath(link)
                
                # Convert back slashes to forward slashes
                target_path = target_path.replace(os.path.sep, '/')
                
                # Add to tracking
                if target_path not in all_links:
                    all_links[target_path] = []
                all_links[target_path].append(file)
                
        except Exception as e:
            logger.error(f"Error analyzing file {file}: {e}")
            continue
    
    # Find orphaned files (files with no incoming links)
    orphaned = []
    for file in files:
        # Normalize file path
        normalized_file = file.replace(os.path.sep, '/')
        
        # Skip index files
        if file.endswith(('index.adoc', 'index.asciidoc')):
            continue
        
        # Skip .gitignore and other git files
        if file.startswith('.git'):
            continue
            
        # Check if file has any incoming links
        if normalized_file not in all_links:
            orphaned.append(file)
    
    # Find wanted files (links to non-existent files)
    wanted = []
    for target_path, source_files in all_links.items():
        # Check if target exists
        full_path = os.path.join(project_path, target_path)
        if not os.path.exists(full_path):
            wanted.append({
                'target': target_path,
                'sources': source_files
            })
    
    # Categorize orphaned files by type
    orphaned_by_type = {
        'documents': [],
        'images': [],
        'pdfs': [],
        'other': []
    }
    
    for file in orphaned:
        ext = os.path.splitext(file)[1].lower()
        if ext in ['.adoc', '.asciidoc', '.txt', '.md']:
            orphaned_by_type['documents'].append(file)
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']:
            orphaned_by_type['images'].append(file)
        elif ext in ['.pdf']:
            orphaned_by_type['pdfs'].append(file)
        else:
            orphaned_by_type['other'].append(file)
    
    # Sort results
    for category in orphaned_by_type.values():
        category.sort()
    wanted.sort(key=lambda x: x['target'])
    
    logger.info(f"Found {len(orphaned)} orphaned files and {len(wanted)} wanted files")
    
    return {
        'orphaned': orphaned,
        'orphaned_by_type': orphaned_by_type,
        'wanted': wanted
    }


def generate_special_page(files: List[str], project_path: str) -> str:
    """
    Generate a special maintenance page with orphaned and wanted files.
    
    Args:
        files: List of file paths in the project
        project_path: Base path of the project
        
    Returns:
        AsciiDoc formatted special page
    """
    analysis = analyze_wiki_structure(files, project_path)
    
    result = "= Wiki Wartung\n\n"
    result += "Diese Spezialseite hilft bei der Wartung des Wikis.\n\n"
    
    # Orphaned files section
    result += "== Verwaiste Dateien\n\n"
    result += f"Dateien ohne eingehende Links: *{len(analysis['orphaned'])}*\n\n"
    
    orphaned_by_type = analysis['orphaned_by_type']
    
    # Documents
    if orphaned_by_type['documents']:
        result += "=== Dokumente\n\n"
        result += f"Verwaiste Dokumente: *{len(orphaned_by_type['documents'])}*\n\n"
        for page in orphaned_by_type['documents']:
            result += f"* link:{page}[{page}]\n"
        result += "\n"
    
    # Images
    if orphaned_by_type['images']:
        result += "=== Bilder\n\n"
        result += f"Verwaiste Bilder: *{len(orphaned_by_type['images'])}*\n\n"
        for img in orphaned_by_type['images']:
            result += f"* link:{img}[{img}]\n"
        result += "\n"
    
    # PDFs
    if orphaned_by_type['pdfs']:
        result += "=== PDF-Dateien\n\n"
        result += f"Verwaiste PDFs: *{len(orphaned_by_type['pdfs'])}*\n\n"
        for pdf in orphaned_by_type['pdfs']:
            result += f"* link:{pdf}[{pdf}]\n"
        result += "\n"
    
    # Other files
    if orphaned_by_type['other']:
        result += "=== Andere Dateien\n\n"
        result += f"Andere verwaiste Dateien: *{len(orphaned_by_type['other'])}*\n\n"
        for other in orphaned_by_type['other']:
            result += f"* link:{other}[{other}]\n"
        result += "\n"
    
    if not analysis['orphaned']:
        result += "_Keine verwaisten Dateien gefunden._\n\n"
    
    # Wanted files section
    result += "== Gewünschte Dateien\n\n"
    result += f"Links zu nicht vorhandenen Dateien: *{len(analysis['wanted'])}*\n\n"
    
    if analysis['wanted']:
        result += "Diese Dateien werden verlinkt, existieren aber nicht:\n\n"
        for item in analysis['wanted']:
            result += f"=== {item['target']}\n\n"
            result += "Verlinkt von:\n\n"
            for source in item['sources']:
                result += f"* link:{source}[{source}]\n"
            result += "\n"
    else:
        result += "_Alle verlinkten Dateien existieren._\n"
    
    result += "\n"
    
    # Statistics
    result += "== Statistik\n\n"
    
    all_file_count = len(files)
    adoc_files = [f for f in files if f.endswith(('.adoc', '.asciidoc'))]
    image_files = [f for f in files if f.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'))]
    pdf_files = [f for f in files if f.endswith('.pdf')]
    
    result += f"* Gesamtzahl Dateien: *{all_file_count}*\n"
    result += f"* Dokumente (.adoc): *{len(adoc_files)}*\n"
    result += f"* Bilder: *{len(image_files)}*\n"
    result += f"* PDF-Dateien: *{len(pdf_files)}*\n"
    result += f"* Andere Dateien: *{all_file_count - len(adoc_files) - len(image_files) - len(pdf_files)}*\n"
    result += "\n"
    result += f"* Verwaiste Dateien: *{len(analysis['orphaned'])}*\n"
    result += f"  ** Dokumente: *{len(orphaned_by_type['documents'])}*\n"
    result += f"  ** Bilder: *{len(orphaned_by_type['images'])}*\n"
    result += f"  ** PDFs: *{len(orphaned_by_type['pdfs'])}*\n"
    result += f"  ** Andere: *{len(orphaned_by_type['other'])}*\n"
    result += "\n"
    result += f"* Gewünschte Dateien: *{len(analysis['wanted'])}*\n"
    result += f"* Dateien mit Links: *{all_file_count - len(analysis['orphaned'])}*\n"
    
    return result


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
