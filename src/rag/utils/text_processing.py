"""Enhanced text processing utilities with comprehensive error handling and validation."""

import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

from openai import OpenAI

from ...server_logging import get_logger

logger = get_logger(__name__)


def extract_url_root_domain(url: str) -> str:
    """Extract root domain from URL with comprehensive handling of various formats.

    This function handles various URL formats and special cases including:
    - URLs with and without protocols
    - International domains with country codes
    - Subdomains and complex domain structures

    Args:
        url: URL string to process

    Returns:
        Root domain string

    Examples:
        >>> extract_url_root_domain("https://www.example.com/path")
        "example.com"
        >>> extract_url_root_domain("sub.example.co.uk")
        "example.co.uk"
        >>> extract_url_root_domain("https://blog.company.com:8080/article")
        "company.com"
    """
    if not url:
        logger.warning("Empty URL provided to extract_url_root_domain")
        return ""

    try:
        # Ensure URL has protocol for proper parsing
        if not url.startswith(("http://", "https://")):
            url = "http://" + url

        # Parse URL and extract netloc (network location)
        parsed = urlparse(url)
        netloc = parsed.netloc

        if not netloc:
            # Fallback if parsing fails
            netloc = url

        # Remove port number if present
        netloc = netloc.split(":")[0]

        # Split domain into parts
        parts = netloc.split(".")

        if len(parts) < 2:
            logger.warning(f"Invalid domain format: {netloc}")
            return netloc

        # Handle special country code domains (e.g., .co.uk, .com.cn)
        if len(parts) > 2:
            # Common second-level domains with country codes
            second_level_domains = {"co", "com", "org", "gov", "edu", "net", "ac"}
            country_codes = {"uk", "cn", "jp", "br", "in", "au", "de", "fr", "it", "es"}

            if len(parts) >= 3 and parts[-2] in second_level_domains and parts[-1] in country_codes:
                return ".".join(parts[-3:])

        # Return main domain (last two parts)
        return ".".join(parts[-2:])

    except Exception as e:
        logger.error(f"Error extracting domain from URL '{url}': {e}")
        return url  # Return original URL as fallback


def get_clean_content(line: str) -> str:
    """Clean and normalize text content by removing formatting artifacts.

    This function removes common formatting elements like:
    - List markers (bullets, numbers, dashes)
    - Leading/trailing quotes
    - Extra whitespace

    Args:
        line: Text line to clean

    Returns:
        Cleaned text string

    Examples:
        >>> get_clean_content("• This is a bullet point")
        "This is a bullet point"
        >>> get_clean_content('"Quoted text"')
        "Quoted text"
        >>> get_clean_content("1. First item")
        "First item"
    """
    if not line:
        return ""

    try:
        # Remove list markers (bullets, numbers, dashes) from the beginning
        clean_line = re.sub(r"^[\*\-•#\d\.]+\s*", "", line).strip()

        # Remove leading and trailing quotes
        clean_line = re.sub(r'^[\'"]|[\'"]$', "", clean_line).strip()

        # Handle wrapped quotes
        if (clean_line.startswith('"') and clean_line.endswith('"')) or (
            clean_line.startswith("'") and clean_line.endswith("'")
        ):
            clean_line = clean_line[1:-1]

        return clean_line.strip()

    except Exception as e:
        logger.error(f"Error cleaning content '{line[:50]}...': {e}")
        return line  # Return original line as fallback


def get_content_from_tag(content: str, tag: str, default_value: Optional[str] = None) -> Optional[str]:
    """Extract content from XML-like tags with robust parsing.

    This function uses advanced regex patterns to extract content between
    XML-like tags, handling various edge cases and malformed content.

    Args:
        content: Text content to search in
        tag: Tag name to search for (without angle brackets)
        default_value: Value to return if tag is not found

    Returns:
        Extracted content or default value

    Examples:
        >>> get_content_from_tag("<summary>This is content</summary>", "summary")
        "This is content"
        >>> get_content_from_tag("<info>Data<other>nested</other>", "info")
        "Data"
    """
    if not content or not tag:
        return default_value

    try:
        # Create pattern that matches content until closing tag or another opening tag
        # Uses lazy matching (.*?) and lookahead to stop at appropriate boundaries
        pattern = rf"<{re.escape(tag)}>(.*?)(?=(</{re.escape(tag)}>|<\w+|$))"

        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            extracted = match.group(1).strip()
            logger.debug(f"Successfully extracted content from tag '{tag}': {len(extracted)} characters")
            return extracted
        else:
            logger.debug(f"Tag '{tag}' not found in content")
            return default_value

    except Exception as e:
        logger.error(f"Error extracting content from tag '{tag}': {e}")
        return default_value


def get_response_from_llm(
    messages: list[dict[str, Any]],
    client: OpenAI,
    model: str,
    stream: bool = False,
    temperature: float = 0.6,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> dict[str, str]:
    """Get response from Language Model with comprehensive error handling and retry logic.

    This function provides robust interaction with OpenAI's API including:
    - Automatic retry on transient failures
    - Exponential backoff for rate limiting
    - Comprehensive error handling
    - Content filtering detection

    Args:
        messages: List of message dictionaries for the conversation
        client: OpenAI client instance
        model: Model name to use
        stream: Whether to use streaming response
        temperature: Sampling temperature (0.0 to 1.0)
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries in seconds

    Returns:
        Dictionary containing the response content

    Raises:
        Exception: If all retry attempts fail
    """
    if not messages:
        logger.error("Empty messages list provided to LLM")
        return {"content": ""}

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"LLM request attempt {attempt + 1}/{max_retries + 1}")

            response = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature, stream=stream
            )

            # Extract content from response
            if hasattr(response.choices[0].message, "content") and response.choices[0].message.content:
                content = response.choices[0].message.content.strip()
                logger.debug(f"LLM response received: {len(content)} characters")
                return {"content": content}
            else:
                logger.warning("LLM response has no content")
                return {"content": ""}

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"LLM API error on attempt {attempt + 1}: {error_msg}")

            # Handle specific error cases
            if "inappropriate content" in error_msg.lower():
                logger.error("Content filtered by LLM safety systems")
                return {"content": ""}

            if "error code: 400" in error_msg.lower():
                logger.error("Bad request to LLM API")
                return {"content": ""}

            if "rate limit" in error_msg.lower():
                # Exponential backoff for rate limiting
                delay = retry_delay * (2**attempt)
                logger.info(f"Rate limited, waiting {delay} seconds before retry")
                time.sleep(delay)
                continue

            # For other errors, wait before retry
            if attempt < max_retries:
                delay = retry_delay
