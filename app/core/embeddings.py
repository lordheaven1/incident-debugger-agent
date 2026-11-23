import hashlib
import math
import os
import re
from dotenv import load_dotenv

load_dotenv()

EMBEDDING_DIM = 384


def _fallback_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    if not tokens:
        return vec
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.embed_content(
                model="gemini-embedding-001",
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            return [list(emb.values) for emb in response.embeddings]
        except Exception as exc:
            print(f"[embeddings] Gemini embedding API unavailable ({exc}), using fallback.")
    return [_fallback_embed(t) for t in texts]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]