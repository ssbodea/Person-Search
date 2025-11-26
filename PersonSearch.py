import requests
import time
from typing import List, Dict, Set, Optional, Any
from nameparser import HumanName
from rapidfuzz import fuzz, process
from urllib.parse import urlparse
import logging
from dataclasses import dataclass
import re
import os

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyCeucm4-CiX6_SKN5QpF7psqCkUgOvQTGk")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "f2d5afa7da2074e5c")

TIMEOUT = 30
REQUEST_DELAY = 1


@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    score: int = 0


class DuckDuckGoSearcher:
    """Free search supplement using DuckDuckGo"""

    def __init__(self):
        try:
            from duckduckgo_search import DDGS

            self.DDGS = DDGS
            self.available = True
            logger.info("DuckDuckGo search available")
        except ImportError:
            logger.warning(
                "DuckDuckGo not available. Install: pip install duckduckgo-search"
            )
            self.available = False

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search using DuckDuckGo"""
        if not self.available:
            return []

        try:
            results = []
            with self.DDGS() as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    if self._is_valid_url(item.get("href", "")):
                        results.append(
                            SearchResult(
                                title=item.get("title", ""),
                                link=item.get("href", ""),
                                snippet=item.get("body", ""),
                            )
                        )
            logger.info(f"DuckDuckGo found {len(results)} results for: {query}")
            return results
        except Exception as e:
            logger.error(f"DuckDuckGo search failed for '{query}': {e}")
            return []

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False


class PersonSearch:
    def __init__(self, api_key: str = GOOGLE_API_KEY, cse_id: str = GOOGLE_CSE_ID):
        self.api_key = api_key
        self.cse_id = cse_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        # Initialize DuckDuckGo searcher
        self.ddg_searcher = DuckDuckGoSearcher()

    def google_search(self, query: str) -> Dict[str, Any]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": self.api_key, "cx": self.cse_id, "q": query, "num": 10}

        try:
            response = self.session.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return {"items": []}

    def extract_results(self, json_data: Dict[str, Any]) -> List[SearchResult]:
        results = []
        items = json_data.get("items", [])

        for item in items:
            try:
                title = item.get("title", "").strip()
                link = item.get("link", "").strip()
                snippet = item.get("snippet", "").strip()

                if link and self._is_valid_url(link):
                    results.append(
                        SearchResult(title=title, link=link, snippet=snippet)
                    )
            except Exception as e:
                logger.warning(f"Error parsing result: {e}")
                continue

        return results

    def _is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def parse_name(self, full_name: str) -> Dict[str, str]:
        if not full_name or not isinstance(full_name, str):
            return self._empty_name_parts()

        full_name = full_name.strip()
        if not full_name:
            return self._empty_name_parts()

        try:
            n = HumanName(full_name)
            return {
                "full": full_name,
                "first": n.first,
                "middle": n.middle,
                "last": n.last,
                "f_initial": n.first[0] if n.first else "",
                "m_initial": n.middle[0] if n.middle else "",
                "l_initial": n.last[0] if n.last else "",
            }
        except Exception as e:
            logger.warning(f"Name parsing failed for '{full_name}': {e}")
            return self._empty_name_parts(full_name)

    def _empty_name_parts(self, full_name: str = "") -> Dict[str, str]:
        return {
            "full": full_name,
            "first": "",
            "middle": "",
            "last": "",
            "f_initial": "",
            "m_initial": "",
            "l_initial": "",
        }

    def generate_name_variations(self, parts: Dict[str, str]) -> List[str]:
        first = parts["first"].lower() if parts["first"] else ""
        middle = parts["middle"].lower() if parts["middle"] else ""
        last = parts["last"].lower() if parts["last"] else ""
        f_initial = parts["f_initial"].lower() if parts["f_initial"] else ""
        m_initial = parts["m_initial"].lower() if parts["m_initial"] else ""
        l_initial = parts["l_initial"].lower() if parts["l_initial"] else ""

        candidates = set()
        separators = ["", ".", "-", "_"]

        if first:
            candidates.add(first)
        if last:
            candidates.add(last)
        if middle:
            candidates.add(middle)

        if first and last:
            for sep in separators:
                candidates.add(f"{first}{sep}{last}")
                candidates.add(f"{last}{sep}{first}")

        if f_initial and last:
            for sep in separators:
                candidates.add(f"{f_initial}{sep}{last}")
                candidates.add(f"{last}{sep}{f_initial}")

        if first and l_initial:
            for sep in separators:
                candidates.add(f"{first}{sep}{l_initial}")
                candidates.add(f"{l_initial}{sep}{first}")

        if f_initial and l_initial:
            for sep in separators:
                candidates.add(f"{f_initial}{sep}{l_initial}")
                candidates.add(f"{l_initial}{sep}{f_initial}")

        if first and middle and last:
            for sep1 in separators:
                for sep2 in separators:
                    candidates.add(f"{first}{sep1}{middle}{sep2}{last}")
                    candidates.add(f"{first}{sep1}{m_initial}{sep2}{last}")

        if f_initial and middle and last:
            for sep1 in separators:
                for sep2 in separators:
                    candidates.add(f"{f_initial}{sep1}{middle}{sep2}{last}")
                    candidates.add(f"{f_initial}{sep1}{m_initial}{sep2}{last}")

        if first and m_initial and last:
            for sep1 in separators:
                for sep2 in separators:
                    candidates.add(f"{first}{sep1}{m_initial}{sep2}{last}")

        if f_initial and m_initial and l_initial:
            for sep1 in separators:
                for sep2 in separators:
                    candidates.add(f"{f_initial}{sep1}{m_initial}{sep2}{l_initial}")

        if parts["full"]:
            full_lower = parts["full"].lower()
            for sep in separators:
                if sep:
                    candidates.add(full_lower.replace(" ", sep))
            candidates.add(full_lower.replace(" ", ""))

        if first and last:
            for sep in separators:
                candidates.add(f"{last}{sep}{first}")

        return [c for c in candidates if c and len(c) > 1]

    def extract_username_from_url(self, url: str) -> str:
        if not url:
            return ""

        url = url.lower()
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            domain = parsed.netloc

            if "linkedin.com" in domain:
                patterns = [r"/in/([^/?]+)", r"/pub/([^/?]+)", r"/([^/?]+)/?$"]
                for pattern in patterns:
                    match = re.search(pattern, "/" + path)
                    if match:
                        username = match.group(1)
                        username = re.sub(r"-[0-9a-z]+$", "", username)
                        if username and len(username) > 1:
                            return username

            elif "facebook.com" in domain or "fb.com" in domain:
                if any(
                    x in path for x in ["/photos/", "/events/", "/groups/", "/posts/"]
                ):
                    return ""

                patterns = [
                    r"^/([^/?]+)(?:\?|$)",
                    r"/people/([^/?]+)",
                    r"/(?:pages|public)/([^/?]+)",
                ]
                for pattern in patterns:
                    match = re.search(pattern, "/" + path)
                    if match:
                        username = match.group(1)
                        skip_words = {
                            "profile",
                            "people",
                            "pages",
                            "public",
                            "home",
                            "watch",
                            "marketplace",
                        }
                        if (
                            username
                            and not username.isdigit()
                            and username not in skip_words
                            and len(username) > 1
                        ):
                            return username

            elif "instagram.com" in domain:
                if any(x in path for x in ["/p/", "/reel/", "/stories/", "/tv/"]):
                    return ""

                segments = [s for s in path.split("/") if s]
                if segments and not any(
                    segments[0] in x for x in ["p/", "reel/", "stories/"]
                ):
                    username = segments[0]
                    if username and not username.isdigit() and len(username) > 1:
                        return username

            segments = [s for s in path.split("/") if s]
            skip_segments = {
                "profile",
                "people",
                "pages",
                "public",
                "p",
                "reel",
                "stories",
                "home",
                "watch",
                "marketplace",
                "events",
                "groups",
                "photos",
                "posts",
            }

            for segment in reversed(segments):
                if (
                    segment
                    and not segment.isdigit()
                    and segment not in skip_segments
                    and len(segment) > 1
                ):
                    if re.search(r"[a-z]", segment):
                        return segment

            return ""

        except Exception as e:
            logger.debug(f"URL extraction failed for {url}: {e}")
            return ""

    def fuzzy_name_match(
        self, text: str, candidates: List[str], threshold: int = 75
    ) -> bool:
        if not text or not candidates:
            return False

        text = text.lower()
        best_match = process.extractOne(text, candidates, score_cutoff=threshold)
        return best_match is not None

    def compute_score(
        self,
        result: SearchResult,
        name_variations: List[str],
        extra_keywords: Optional[List[str]] = None,
    ) -> int:
        """Compute relevance score using URL-based fuzzy matching"""
        score = 0

        # Extract username from URL and fuzzy match against name variations
        extracted_username = self.extract_username_from_url(result.link)

        if extracted_username:
            # Fuzzy match the extracted username against name variations
            username_match = self.fuzzy_name_match(
                extracted_username, name_variations, 80
            )
            if username_match:
                score = 3  # Strong match based on username

        # If no URL match, check title and snippet
        if score == 0:
            text_to_check = (result.title + " " + result.snippet).lower()
            text_match = self.fuzzy_name_match(text_to_check, name_variations, 70)
            if text_match:
                score = 1  # Weaker match based on content

        # Boost for social media platforms
        link_lower = result.link.lower()
        if any(
            platform in link_lower
            for platform in ["linkedin.com", "facebook.com", "instagram.com"]
        ):
            score += 1

        # Extra keywords scoring
        if extra_keywords and score > 0:
            text_to_check = (result.title + " " + result.snippet).lower()
            for keyword in extra_keywords:
                if keyword.lower() in text_to_check:
                    score += 1

        return score

    def build_queries(self, name: str) -> List[str]:
        base_queries = [
            f'"{name}" site:linkedin.com/in/',
            f'"{name}" site:linkedin.com/pub/',
            f'"{name}" "linkedin"',
            f'"{name}" site:facebook.com',
            f'"{name}" "facebook"',
            f'"{name}" "facebook profile"',
            f'"{name}" site:instagram.com',
            f'"{name}" "instagram"',
            f'"{name}" "instagram profile"',
        ]

        return base_queries

    def remove_duplicates(self, results: List[SearchResult]) -> List[SearchResult]:
        seen_urls = set()
        unique_results = []

        for result in results:
            if result.link not in seen_urls:
                seen_urls.add(result.link)
                unique_results.append(result)

        return unique_results

    def search_person(
        self, name: str, extra_info: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if not name or not name.strip():
            logger.error("No name provided for search")
            return []

        logger.info(f"Starting search for: {name}")

        try:
            parts = self.parse_name(name)
            name_variations = self.generate_name_variations(parts)
            queries = self.build_queries(name)

            all_results = []

            for i, query in enumerate(queries):
                logger.info(f"Searching query {i+1}/{len(queries)}: {query}")

                try:
                    # Search with Google CSE (primary)
                    google_data = self.google_search(query)
                    google_results = self.extract_results(google_data)
                    all_results.extend(google_results)
                    logger.info(f"Google returned {len(google_results)} results")

                    # Supplement with DuckDuckGo (free, no limits)
                    ddg_results = self.ddg_searcher.search(query)
                    all_results.extend(ddg_results)
                    logger.info(f"DuckDuckGo added {len(ddg_results)} results")

                    if i < len(queries) - 1:
                        time.sleep(REQUEST_DELAY)

                except Exception as e:
                    logger.error(f"Query failed '{query}': {e}")
                    continue

            unique_results = self.remove_duplicates(all_results)
            logger.info(
                f"Total unique results after deduplication: {len(unique_results)}"
            )

            scored_results = []
            for result in unique_results:
                score = self.compute_score(result, name_variations, extra_info)
                if score > 0:
                    result.score = score
                    scored_results.append(result)

            scored_results.sort(key=lambda x: x.score, reverse=True)

            logger.info(
                f"Search completed. Found {len(scored_results)} relevant results."
            )
            return [self._result_to_dict(r) for r in scored_results]

        except Exception as e:
            logger.error(f"Search failed unexpectedly: {e}")
            return []

    def _result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        return {
            "title": result.title,
            "link": result.link,
            "snippet": result.snippet,
            "score": result.score,
        }


def main():
    searcher = PersonSearch()

    try:
        name = input("Enter the name to search: ").strip()
        if not name:
            print("Error: No name provided.")
            return

        extra_input = input(
            "Extra info (city, education, occupation - comma separated, or press Enter to skip): "
        ).strip()
        extra_keywords = (
            [x.strip() for x in extra_input.split(",")] if extra_input else None
        )

        print(f"\nSearching for '{name}'... This may take a moment.\n")

        results = searcher.search_person(name, extra_keywords)

        print(f"Found {len(results)} relevant results:\n")

        for i, result in enumerate(results, 1):
            print(f"Result #{i}:")
            print(f"  Score:   {result['score']}")
            print(f"  Title:   {result['title']}")
            print(f"  Link:    {result['link']}")
            if result["snippet"]:
                print(f"  Snippet: {result['snippet'][:150]}...")
            print("-" * 80)

    except KeyboardInterrupt:
        print("\nSearch cancelled by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()