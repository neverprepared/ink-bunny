#!/usr/bin/env python3
"""
Automatically store WebSearch results in Qdrant vector database.

Called by qdrant-websearch-hook.sh PostToolUse hook.
Extracts metadata, synthesizes content, and stores to Qdrant.

Fail-open design: exits silently on all errors to avoid blocking WebSearch.
"""

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


# =============================================================================
# Configuration
# =============================================================================

def get_collection_name() -> str:
    """Get Qdrant collection name from environment."""
    # Try workspace-specific collection first
    workspace = os.getenv("WORKSPACE_PROFILE", "")
    if workspace:
        workspace_name = os.path.basename(workspace.rstrip("/"))
        return f"{workspace_name}_memories"

    # Fallback to default
    return os.getenv("COLLECTION_NAME", "default_memories")


QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = get_collection_name()
VECTOR_NAME = "fast-all-minilm-l6-v2"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# =============================================================================
# Metadata Extraction Heuristics
# =============================================================================

# Category keywords (technology subcategories)
TECH_CATEGORIES = {
    "databases": ["postgres", "mysql", "mongodb", "redis", "qdrant", "elasticsearch", "database", "sql", "nosql"],
    "frontend": ["react", "vue", "angular", "svelte", "css", "html", "javascript", "typescript", "webpack", "vite"],
    "backend": ["fastapi", "django", "flask", "express", "node", "api", "rest", "graphql"],
    "devops": ["docker", "kubernetes", "k8s", "terraform", "ansible", "ci/cd", "jenkins", "github actions"],
    "ml": ["machine learning", "tensorflow", "pytorch", "sklearn", "ml", "ai", "neural network"],
    "security": ["security", "auth", "oauth", "jwt", "encryption", "vulnerability", "penetration"],
    "cloud": ["aws", "azure", "gcp", "cloud", "lambda", "s3", "ec2"],
    "networking": ["http", "tcp", "dns", "nginx", "proxy", "load balancer"],
}

# Main categories
CATEGORIES = {
    "technology": list(TECH_CATEGORIES.keys()),
    "business": ["startup", "marketing", "sales", "strategy", "finance"],
    "science": ["research", "paper", "study", "experiment", "academic"],
    "design": ["ui", "ux", "design", "figma", "sketch", "wireframe"],
}

# Programming languages
LANGUAGES = [
    "python", "javascript", "typescript", "go", "rust", "java", "c++", "cpp",
    "ruby", "php", "swift", "kotlin", "scala", "haskell", "elixir", "bash"
]

# Frameworks
FRAMEWORKS = [
    "react", "vue", "angular", "svelte", "nextjs", "nuxt",
    "fastapi", "django", "flask", "express", "nestjs",
    "spring", "rails", "laravel", "asp.net"
]


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return None


def categorize_by_keywords(text: str) -> Tuple[str, Optional[str]]:
    """
    Categorize query/results using keyword matching.

    Returns:
        (category, subcategory) tuple
    """
    text_lower = text.lower()

    # Check technology subcategories first
    for subcategory, keywords in TECH_CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return ("technology", subcategory)

    # Check main categories
    for category, keywords in CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return (category, None)

    # Default to technology
    return ("technology", None)


def infer_type_from_query(query: str) -> str:
    """
    Infer content type from query intent.

    Returns:
        One of: tutorial, troubleshooting, comparison, reference, documentation
    """
    query_lower = query.lower()

    # Tutorial indicators
    if any(word in query_lower for word in ["how to", "guide", "tutorial", "learn", "getting started"]):
        return "tutorial"

    # Troubleshooting indicators
    if any(word in query_lower for word in ["error", "fix", "debug", "problem", "issue", "not working", "fails"]):
        return "troubleshooting"

    # Comparison indicators
    if any(word in query_lower for word in [" vs ", " versus ", "compare", "difference between", "better than"]):
        return "comparison"

    # Documentation indicators
    if any(word in query_lower for word in ["documentation", "docs", "api reference", "specification"]):
        return "documentation"

    # Default to reference
    return "reference"


def extract_language(text: str) -> Optional[str]:
    """Extract programming language from text."""
    text_lower = text.lower()
    for lang in LANGUAGES:
        if lang in text_lower:
            return lang
    return None


def extract_framework(text: str) -> Optional[str]:
    """Extract framework from text."""
    text_lower = text.lower()
    for fw in FRAMEWORKS:
        if fw in text_lower:
            return fw
    return None


def extract_related_topics(query: str, results: List[Dict]) -> List[str]:
    """
    Extract related topics from query and result titles.

    Returns:
        List of topic keywords (max 5)
    """
    # Extract significant words from query (skip common words)
    stop_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "how", "what", "why", "when"}
    query_words = [w.lower() for w in re.findall(r'\w+', query) if w.lower() not in stop_words]

    # Extract words from result titles
    title_words = []
    for result in results[:3]:  # Only top 3 results
        title = result.get("title", "")
        title_words.extend([w.lower() for w in re.findall(r'\w+', title) if w.lower() not in stop_words])

    # Combine and deduplicate
    all_words = query_words + title_words
    word_freq = {}
    for word in all_words:
        if len(word) > 3:  # Skip short words
            word_freq[word] = word_freq.get(word, 0) + 1

    # Return top 5 most frequent
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:5]]


def calculate_confidence(results: List[Dict]) -> str:
    """
    Calculate confidence level based on result quality.

    Returns:
        One of: high, medium, low
    """
    if not results:
        return "low"

    # Check for reputable domains
    reputable_domains = {
        "github.com", "stackoverflow.com", "docs.python.org", "developer.mozilla.org",
        "microsoft.com", "aws.amazon.com", "google.com", "wikipedia.org"
    }

    reputable_count = 0
    for result in results[:5]:
        url = result.get("url", "")
        domain = extract_domain(url)
        if domain in reputable_domains:
            reputable_count += 1

    # Confidence based on reputable sources and result count
    if len(results) >= 5 and reputable_count >= 2:
        return "high"
    elif len(results) >= 3:
        return "medium"
    else:
        return "low"


def infer_freshness(query: str) -> str:
    """
    Infer expected freshness from query.

    Returns:
        One of: current, recent, dated
    """
    query_lower = query.lower()

    # Time-sensitive indicators
    if any(word in query_lower for word in ["latest", "new", "2026", "2025", "current", "today", "recent"]):
        return "current"

    # General queries (assume recent)
    return "recent"


def build_metadata(tool_input: Dict, tool_response: List[Dict]) -> Dict:
    """Build metadata from WebSearch tool input and response."""
    query = tool_input.get("query", "")
    results = tool_response if isinstance(tool_response, list) else []

    # Extract URLs from results
    urls = [r.get("url", "") for r in results if r.get("url")][:5]  # Top 5 URLs

    # Extract primary domain (from first result)
    domain = extract_domain(urls[0]) if urls else None

    # Categorize
    combined_text = query + " " + " ".join([r.get("title", "") + " " + r.get("snippet", "") for r in results[:3]])
    category, subcategory = categorize_by_keywords(combined_text)

    # Build metadata
    metadata = {
        # Required
        "source": "web_search",
        "content_type": "text",
        "harvested_at": datetime.now().isoformat(),

        # Search context
        "query": query,
        "urls": urls,

        # Classification
        "category": category,
        "type": infer_type_from_query(query),

        # Quality
        "confidence": calculate_confidence(results),
        "freshness": infer_freshness(query),

        # Relationships
        "related_topics": extract_related_topics(query, results),
    }

    # Optional fields
    if domain:
        metadata["domain"] = domain
    if subcategory:
        metadata["subcategory"] = subcategory

    language = extract_language(combined_text)
    if language:
        metadata["language"] = language

    framework = extract_framework(combined_text)
    if framework:
        metadata["framework"] = framework

    return metadata


def synthesize_content(tool_input: Dict, tool_response: List[Dict]) -> str:
    """
    Synthesize search results into a markdown document.

    Args:
        tool_input: WebSearch tool input (contains query)
        tool_response: WebSearch tool response (contains results)

    Returns:
        Markdown-formatted content
    """
    query = tool_input.get("query", "Unknown query")
    results = tool_response if isinstance(tool_response, list) else []

    lines = [
        f"# Web Search: {query}",
        "",
        f"**Query:** {query}",
        f"**Searched:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Results:** {len(results)} sources",
        "",
        "## Search Results",
        ""
    ]

    for i, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        snippet = result.get("snippet", "")

        lines.append(f"### {i}. {title}")
        if url:
            lines.append(f"**URL:** {url}")
        if snippet:
            lines.append(f"\n{snippet}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Qdrant Storage
# =============================================================================

def store_to_qdrant(content: str, metadata: Dict) -> None:
    """
    Store content to Qdrant with metadata.

    Args:
        content: Document content
        metadata: Metadata dictionary

    Raises:
        All exceptions are caught and suppressed (fail-open design)
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct, VectorParams, Distance
        from fastembed import TextEmbedding
    except ImportError:
        # Missing dependencies, exit silently
        return

    try:
        # Connect to Qdrant
        client = QdrantClient(url=QDRANT_URL, timeout=5)

        # Ensure collection exists
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    VECTOR_NAME: VectorParams(size=384, distance=Distance.COSINE)
                }
            )

        # Generate embedding
        embedder = TextEmbedding(MODEL_NAME)
        embedding = list(embedder.embed([content]))[0]

        # Generate point ID from content hash (prevents duplicates)
        # Qdrant requires UUID or unsigned int — convert MD5 hex to UUID
        point_id = str(uuid.UUID(hex=hashlib.md5(content.encode()).hexdigest()))

        # Create point
        point = PointStruct(
            id=point_id,
            vector={VECTOR_NAME: embedding.tolist()},
            payload={
                "document": content,
                "metadata": metadata
            }
        )

        # Upsert (will update if exists, insert if new)
        client.upsert(collection_name=COLLECTION_NAME, points=[point])

    except Exception:
        # Fail silently on any error (Qdrant down, network issue, etc.)
        pass


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point for hook script."""
    try:
        # Read tool data from stdin
        tool_data = json.loads(sys.stdin.read())

        # Extract tool input and response
        tool_input = tool_data.get("tool_input", {})
        tool_response = tool_data.get("tool_response", [])

        # Skip if no results
        if not tool_response:
            return

        # Build metadata
        metadata = build_metadata(tool_input, tool_response)

        # Synthesize content
        content = synthesize_content(tool_input, tool_response)

        # Store to Qdrant
        store_to_qdrant(content, metadata)

    except Exception:
        # Fail silently on any error
        pass


if __name__ == "__main__":
    main()
