from .heuristic import Classification, classify as classify_heuristic
from .ollama_classifier import classify

__all__ = ["Classification", "classify", "classify_heuristic"]
