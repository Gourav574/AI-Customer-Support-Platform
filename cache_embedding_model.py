"""Explicitly download/cache the configured Sentence Transformer weights."""
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ["EMBEDDING_DOWNLOAD_MODEL"]="true"
from sentence_transformers import SentenceTransformer
from backend.app.config import settings
model=SentenceTransformer(settings.embedding_model)
print(f"Cached {settings.embedding_model}; embedding dimension={model.get_sentence_embedding_dimension()}")
