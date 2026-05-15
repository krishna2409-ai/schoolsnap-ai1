import faiss
import numpy as np
import json
import os
from typing import List

class VectorStore:
    def __init__(self, dimension: int = 512):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)  # L2 distance (approximates cosine dist on normalized vectors)
        self.metadata = []  # Metadata for each vector

    def add_embeddings(self, embeddings: List[List[float]], metadata: List[dict]):
        """Add embeddings to FAISS index with associated metadata."""
        if not embeddings:
            return
        
        embeddings_np = np.array(embeddings).astype('float32')
        faiss.normalize_L2(embeddings_np)
        
        self.index.add(embeddings_np)
        self.metadata.extend(metadata)

    def search(
        self,
        query_embeddings: List[List[float]],
        top_k: int = 50,
        threshold: float = 0.3,
        min_support: int = 1
    ) -> List[dict]:
        """Search for similar faces using multiple query embeddings."""
        if not query_embeddings or self.index.ntotal == 0:
            return []
        
        query_np = np.array(query_embeddings).astype('float32')
        faiss.normalize_L2(query_np)
        
        # Search with all query embeddings
        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_np, k)
        
        # Aggregate results — best score per image
        image_scores = {}
        
        print(f"[VectorStore] Search triggered. Results pool: {distances.shape[0]}x{distances.shape[1]}")
        
        for i in range(len(query_embeddings)):
            valid_batch = [d for d in distances[i] if d <= threshold]
            if valid_batch:
                print(f"  [Query {i}] Best: {min(distances[i]):.3f}, Mean: {np.mean(distances[i]):.3f}, Total matches: {len(valid_batch)}")

            for dist, idx in zip(distances[i], indices[i]):
                if idx != -1 and dist <= threshold:
                    meta = self.metadata[idx]
                    image_id = meta.get('image_id', meta['image_path'])

                    if image_id not in image_scores:
                        image_scores[image_id] = {
                            "image_path": meta['image_path'],
                            "image_id": meta.get('image_id', ''),
                            "confidence": float(dist),
                            "bbox": meta['bbox'],
                            "event_id": meta.get('event_id', ''),
                            "support_queries": set(),
                            "hit_count": 0
                        }

                    image_scores[image_id]["hit_count"] += 1
                    image_scores[image_id]["support_queries"].add(i)
                    if dist < image_scores[image_id]['confidence']:
                        image_scores[image_id]['confidence'] = float(dist)
                        image_scores[image_id]['bbox'] = meta['bbox']
        
        filtered = []
        for item in image_scores.values():
            support = len(item["support_queries"])
            if support >= min_support:
                item["support_queries"] = support
                filtered.append(item)

        # Sort by support first (descending), then confidence (ascending because lower distance is better)
        results = sorted(filtered, key=lambda x: (-x['support_queries'], x['confidence']))
        return results[:top_k]

    def save(self, path: str):
        """Save FAISS index and metadata to disk."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        faiss.write_index(self.index, f"{path}.index")
        with open(f"{path}.meta", 'w') as f:
            json.dump(self.metadata, f)

    def load(self, path: str):
        """Load FAISS index and metadata from disk."""
        if os.path.exists(f"{path}.index") and os.path.exists(f"{path}.meta"):
            self.index = faiss.read_index(f"{path}.index")
            with open(f"{path}.meta", 'r') as f:
                self.metadata = json.load(f)
            print(f"[VectorStore] Loaded {self.index.ntotal} vectors from disk")
        else:
            print("[VectorStore] No saved index found, starting fresh")


# Singleton
vector_store = VectorStore()
