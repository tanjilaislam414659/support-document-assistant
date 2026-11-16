"""Fixed BM25 ranking and a shared hit contract; no answerability inference."""
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import math
import re
from typing import Any, Protocol
import unicodedata

from .assets import sha256


SPEC_ID = "bm25-keyword-v1"
K1 = 1.2
B = 0.75
DEFAULT_TOP_K = 5
MAX_TOP_K = 40
MAX_QUERY_CHARACTERS = 4096
TOKEN_PATTERN = r"(?u)(?:--?)?\w+(?:[.-]\w+)*"
TOKEN_RE = re.compile(TOKEN_PATTERN)
CHUNK_ID_RE = re.compile(r"chunk-[0-9a-f]{64}")
SCORE_KIND = "bm25_ranking_score_not_probability"


def tokenize(text: str) -> list[str]:
    """Tokenize the whole text; document inputs are never windowed or truncated."""
    if not isinstance(text, str):
        raise ValueError("Tokenization input must be a string")
    return TOKEN_RE.findall(unicodedata.normalize("NFKC", text).casefold())


def query_tokens(query: str) -> list[str]:
    if not isinstance(query, str):
        raise ValueError("Query must be a string")
    if len(query) > MAX_QUERY_CHARACTERS:
        raise ValueError(f"Query exceeds {MAX_QUERY_CHARACTERS} characters; not truncated")
    if any((ord(c) < 32 and c not in "\t\n\r") or 0xD800 <= ord(c) <= 0xDFFF for c in query):
        raise ValueError("Query contains an invalid control or surrogate code point")
    return sorted(set(tokenize(query)))


def validate_top_k(top_k: int) -> None:
    if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be an integer from 1 through {MAX_TOP_K}")


@dataclass(frozen=True)
class RankedChunk:
    """Original source-linked record plus method-specific ranking fields."""
    rank: int
    score: float
    chunk: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "score": self.score, "chunk": deepcopy(self.chunk)}


class Retriever(Protocol):
    """Later backends may implement this contract; only BM25 exists today."""
    method: str
    score_kind: str
    corpus_build_id: str | None

    def search(self, query: str, *, top_k: int = DEFAULT_TOP_K) -> list[RankedChunk]:
        ...


class BM25Retriever:
    method = "bm25"
    spec_id = SPEC_ID
    score_kind = SCORE_KIND

    def __init__(self, chunks: Sequence[Mapping[str, Any]], *, corpus_build_id: str | None = None):
        if not isinstance(chunks, Sequence) or isinstance(chunks, (str, bytes)):
            raise ValueError("Chunks must be a sequence of source-linked records")
        self.corpus_build_id = corpus_build_id
        self._chunks = []
        seen = set()
        self._lengths = []
        self._postings = defaultdict(list)
        for chunk in chunks:
            if not isinstance(chunk, Mapping):
                raise ValueError("Each chunk must be a record")
            chunk_id = chunk.get("chunk_id")
            if not isinstance(chunk_id, str) or not CHUNK_ID_RE.fullmatch(chunk_id):
                raise ValueError("Malformed chunk ID")
            if chunk_id in seen:
                raise ValueError("Duplicate chunk ID")
            seen.add(chunk_id)
            if chunk.get("eligible_for_answer_support") is not True:
                raise ValueError("Ineligible chunk cannot enter the index")
            for name in ("source_id", "immutable_url", "product_version", "commit"):
                if not isinstance(chunk.get(name), str) or not chunk[name].strip():
                    raise ValueError(f"Missing source metadata: {name}")
            text = chunk.get("text")
            if not isinstance(text, str):
                raise ValueError("Chunk text must be a string")
            if chunk.get("text_sha256") != sha256(text.encode("utf-8")):
                raise ValueError("Chunk text hash mismatch")
            record = deepcopy(dict(chunk))
            index = len(self._chunks)
            self._chunks.append(record)
            frequencies = Counter(tokenize(text))
            self._lengths.append(sum(frequencies.values()))
            for term, frequency in frequencies.items():
                self._postings[term].append((index, frequency))
        self.document_count = len(self._chunks)
        self._average_length = sum(self._lengths) / self.document_count if self.document_count else 0.0

    def search(self, query: str, *, top_k: int = DEFAULT_TOP_K) -> list[RankedChunk]:
        terms = query_tokens(query)
        validate_top_k(top_k)
        if not terms or not self.document_count or not self._average_length:
            return []
        contributions = defaultdict(list)
        for term in terms:
            postings = self._postings.get(term, ())
            if not postings:
                continue
            df = len(postings)
            idf = math.log1p((self.document_count - df + 0.5) / (df + 0.5))
            for index, frequency in postings:
                length_normalization = K1 * (1 - B + B * self._lengths[index] / self._average_length)
                contributions[index].append(idf * frequency * (K1 + 1) /
                                            (frequency + length_normalization))
        scores = [(math.fsum(parts), index) for index, parts in contributions.items()]
        scores = [(score, index) for score, index in scores if score > 0.0]
        scores.sort(key=lambda item: (-item[0], self._chunks[item[1]]["chunk_id"]))
        return [RankedChunk(rank, score, deepcopy(self._chunks[index]))
                for rank, (score, index) in enumerate(scores[:top_k], 1)]
