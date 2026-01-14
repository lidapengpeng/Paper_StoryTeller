"""
ArXiv paper fetching module

Fetches paper metadata and PDFs from arXiv.org
"""

import arxiv
import requests
from typing import Dict, Optional
from pathlib import Path
from loguru import logger
from datetime import datetime

from .utils import extract_arxiv_id, ensure_dir, sanitize_filename


class ArXivFetcher:
    """Fetches papers from arXiv"""

    def __init__(self, temp_dir: str = "temp"):
        """
        Initialize ArXiv fetcher

        Args:
            temp_dir: Directory for temporary file storage
        """
        self.temp_dir = ensure_dir(temp_dir)
        self.client = arxiv.Client()

    def fetch_paper(self, arxiv_url_or_id: str) -> Dict:
        """
        Fetch paper metadata from arXiv

        Args:
            arxiv_url_or_id: arXiv URL or ID (e.g., "https://arxiv.org/abs/1512.03385" or "1512.03385")

        Returns:
            Dictionary with paper metadata:
            {
                'arxiv_id': str,
                'title': str,
                'authors': List[str],
                'abstract': str,
                'pdf_url': str,
                'published': datetime,
                'updated': datetime,
                'categories': List[str],
                'primary_category': str,
                'comment': str,
                'journal_ref': str,
                'doi': str
            }
        """
        arxiv_id = extract_arxiv_id(arxiv_url_or_id)
        logger.info(f"Fetching paper metadata for arXiv ID: {arxiv_id}")

        try:
            # Search for paper by ID
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(self.client.results(search))

            metadata = {
                'arxiv_id': arxiv_id,
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'abstract': paper.summary,
                'pdf_url': paper.pdf_url,
                'published': paper.published,
                'updated': paper.updated,
                'categories': paper.categories,
                'primary_category': paper.primary_category,
                'comment': paper.comment or "",
                'journal_ref': paper.journal_ref or "",
                'doi': paper.doi or ""
            }

            logger.success(f"✅ Fetched metadata for: {metadata['title'][:60]}...")
            logger.info(f"   Authors: {', '.join(metadata['authors'][:3])}{'...' if len(metadata['authors']) > 3 else ''}")
            logger.info(f"   Published: {metadata['published'].strftime('%Y-%m-%d')}")

            return metadata

        except StopIteration:
            logger.error(f"❌ Paper not found: {arxiv_id}")
            raise ValueError(f"Paper not found on arXiv: {arxiv_id}")

        except Exception as e:
            logger.error(f"❌ Error fetching paper {arxiv_id}: {e}")
            raise

    def download_pdf(self, pdf_url: str, arxiv_id: str, output_dir: Optional[str] = None) -> str:
        """
        Download PDF from arXiv

        Args:
            pdf_url: URL to the PDF
            arxiv_id: arXiv ID (for filename)
            output_dir: Directory to save PDF (default: temp_dir)

        Returns:
            Path to downloaded PDF file
        """
        if output_dir is None:
            output_dir = self.temp_dir

        # Create filename
        safe_id = sanitize_filename(arxiv_id)
        pdf_path = Path(output_dir) / f"{safe_id}.pdf"

        # Check if already downloaded
        if pdf_path.exists():
            logger.info(f"📄 PDF already exists: {pdf_path}")
            return str(pdf_path)

        logger.info(f"📥 Downloading PDF from {pdf_url}...")

        try:
            response = requests.get(pdf_url, stream=True, timeout=60)
            response.raise_for_status()

            # Save PDF
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            logger.success(f"✅ Downloaded PDF: {pdf_path} ({file_size_mb:.2f} MB)")

            return str(pdf_path)

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to download PDF: {e}")
            raise

        except Exception as e:
            logger.error(f"❌ Error saving PDF: {e}")
            raise

    def fetch_and_download(self, arxiv_url_or_id: str) -> tuple[Dict, str]:
        """
        Convenience method to fetch metadata and download PDF

        Args:
            arxiv_url_or_id: arXiv URL or ID

        Returns:
            Tuple of (metadata dict, pdf path)
        """
        metadata = self.fetch_paper(arxiv_url_or_id)
        pdf_path = self.download_pdf(metadata['pdf_url'], metadata['arxiv_id'])

        return metadata, pdf_path

    def search_papers(self, query: str, max_results: int = 10) -> list[Dict]:
        """
        Search for papers on arXiv

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of paper metadata dictionaries
        """
        logger.info(f"🔍 Searching arXiv for: '{query}'")

        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )

            results = []
            for paper in self.client.results(search):
                results.append({
                    'arxiv_id': paper.get_short_id(),
                    'title': paper.title,
                    'authors': [author.name for author in paper.authors],
                    'abstract': paper.summary[:200] + "...",  # Truncate
                    'pdf_url': paper.pdf_url,
                    'published': paper.published,
                    'categories': paper.categories
                })

            logger.success(f"✅ Found {len(results)} papers")
            return results

        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            raise


# Example usage
if __name__ == "__main__":
    from .utils import setup_logging

    setup_logging("INFO")

    fetcher = ArXivFetcher()

    # Example 1: Fetch ResNet paper
    print("\n" + "="*50)
    print("Example 1: Fetching ResNet paper")
    print("="*50)

    try:
        metadata, pdf_path = fetcher.fetch_and_download("https://arxiv.org/abs/1512.03385")
        print(f"\nTitle: {metadata['title']}")
        print(f"Authors: {', '.join(metadata['authors'][:3])}...")
        print(f"PDF saved to: {pdf_path}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Search for papers
    print("\n" + "="*50)
    print("Example 2: Searching for Vision Transformer papers")
    print("="*50)

    try:
        results = fetcher.search_papers("Vision Transformer", max_results=5)
        for i, paper in enumerate(results, 1):
            print(f"\n{i}. {paper['title']}")
            print(f"   ID: {paper['arxiv_id']}")
            print(f"   Authors: {', '.join(paper['authors'][:2])}...")
    except Exception as e:
        print(f"Error: {e}")
