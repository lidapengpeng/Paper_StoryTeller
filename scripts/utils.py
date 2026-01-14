"""
Utility functions for Paper Storyteller
"""

import os
import re
import hashlib
import json
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger
from datetime import datetime


def setup_logging(log_level: str = "INFO"):
    """Configure logging with loguru"""
    logger.remove()  # Remove default handler
    logger.add(
        lambda msg: print(msg, end=""),
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
        level=log_level
    )

    # Also log to file
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "paper_storyteller_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level=log_level
    )


def extract_arxiv_id(url_or_id: str) -> str:
    """
    Extract arXiv ID from URL or return the ID if already extracted

    Examples:
        https://arxiv.org/abs/1512.03385 -> 1512.03385
        https://arxiv.org/pdf/1512.03385.pdf -> 1512.03385
        1512.03385 -> 1512.03385
    """
    # If it's already just an ID
    if re.match(r'^\d{4}\.\d{4,5}(v\d+)?$', url_or_id):
        return url_or_id

    # Extract from URL
    patterns = [
        r'arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'arxiv\.org/pdf/(\d{4}\.\d{4,5}(?:v\d+)?)',
        r'(\d{4}\.\d{4,5}(?:v\d+)?)'
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract arXiv ID from: {url_or_id}")


def ensure_dir(path: str) -> Path:
    """Ensure directory exists, create if not"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_cache_path(key: str, cache_dir: str = "cache") -> Path:
    """Get cache file path for a given key"""
    cache_dir_path = ensure_dir(cache_dir)
    key_hash = hashlib.md5(key.encode()).hexdigest()
    return cache_dir_path / f"{key_hash}.json"


def load_from_cache(key: str, cache_dir: str = "cache") -> Optional[Dict]:
    """Load data from cache if exists"""
    cache_path = get_cache_path(key, cache_dir)

    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Loaded from cache: {key}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load cache for {key}: {e}")
            return None

    return None


def save_to_cache(key: str, data: Dict, cache_dir: str = "cache"):
    """Save data to cache"""
    cache_path = get_cache_path(key, cache_dir)

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Saved to cache: {key}")
    except Exception as e:
        logger.warning(f"Failed to save cache for {key}: {e}")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters"""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized


def format_authors(authors: list) -> str:
    """Format list of authors for display"""
    if not authors:
        return "Unknown"

    if len(authors) == 1:
        return authors[0]
    elif len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    elif len(authors) <= 5:
        return ", ".join(authors[:-1]) + f", and {authors[-1]}"
    else:
        return f"{authors[0]} et al. ({len(authors)} authors)"


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """Estimate reading time in minutes"""
    word_count = len(text.split())
    return max(1, round(word_count / words_per_minute))


def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and normalizing"""
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def load_prompt_template(prompt_name: str, prompts_dir: str = "prompts") -> str:
    """Load a prompt template from file"""
    prompt_path = Path(prompts_dir) / f"{prompt_name}.md"

    if not prompt_path.exists():
        logger.warning(f"Prompt template not found: {prompt_path}")
        return ""

    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt template {prompt_name}: {e}")
        return ""


def save_json(data: Dict, filepath: str):
    """Save dictionary as JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: str) -> Dict:
    """Load JSON file as dictionary"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_timestamp() -> str:
    """Get current timestamp as string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class ProgressTracker:
    """Track progress of multi-step operations"""

    def __init__(self, total_steps: int, description: str = "Processing"):
        self.total_steps = total_steps
        self.current_step = 0
        self.description = description

    def update(self, step_name: str):
        """Update progress with current step name"""
        self.current_step += 1
        percentage = (self.current_step / self.total_steps) * 100
        logger.info(f"[{percentage:.1f}%] {self.description}: {step_name}")

    def complete(self):
        """Mark as complete"""
        logger.success(f"✅ {self.description} complete!")


# Layer personification mappings
LAYER_METAPHORS = {
    'conv': "Like eyes scanning an image, looking for small details like edges and textures",
    'relu': "Like the brain filtering out useless information, keeping only strong signals",
    'attention': "Like focusing on important areas while ignoring background noise",
    'pool': "Like summarizing key points from a long article",
    'fc': "Like making a final decision based on all the evidence gathered",
    'bn': "Like normalizing everyone's test scores to make fair comparisons",
    'dropout': "Like randomly forgetting some information to avoid overthinking",
    'softmax': "Like converting scores into percentages that add up to 100%",
    'embedding': "Like converting words into numerical coordinates in meaning-space",
    'lstm': "Like a memory that can remember or forget selectively",
}


def get_layer_metaphor(layer_type: str) -> str:
    """Get metaphor for a neural network layer type"""
    layer_type_lower = layer_type.lower()

    for key, metaphor in LAYER_METAPHORS.items():
        if key in layer_type_lower:
            return metaphor

    return "Like a special processing unit that transforms the data"


if __name__ == "__main__":
    # Test utilities
    setup_logging("DEBUG")

    # Test arXiv ID extraction
    test_urls = [
        "https://arxiv.org/abs/1512.03385",
        "https://arxiv.org/pdf/1512.03385.pdf",
        "1512.03385",
        "1512.03385v2"
    ]

    for url in test_urls:
        arxiv_id = extract_arxiv_id(url)
        logger.info(f"{url} -> {arxiv_id}")

    # Test progress tracker
    tracker = ProgressTracker(5, "Test Process")
    tracker.update("Step 1")
    tracker.update("Step 2")
    tracker.update("Step 3")
    tracker.update("Step 4")
    tracker.update("Step 5")
    tracker.complete()
