from sentence_transformers import SentenceTransformer

EMBEDDING_DIM = 384  # matches all-MiniLM-L6-v2's output size

# Lazy singleton: loading the model takes seconds and ~100MB — do it on first
# use, not at import, so app startup (and anything importing this module
# transitively) stays fast.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def generate_embedding(text: str) -> list[float]:
    """
    Generates a normalized embedding vector for the given text.
    Normalized so cosine similarity reduces to a simple dot product later.
    """
    vector = _get_model().encode(text, normalize_embeddings=True)
    return vector.tolist()
