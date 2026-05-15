from vector_store import vector_store
from ai_service import ai_service
import pprint
import os
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))
vector_store.load(os.path.join(base_dir, 'faiss_store'))

query_path = r'D:\Projects\SNAP!\backend\images\selfies\b51f2a19-e6b4-4022-893a-cce9de5110b9.jpg'
faces = ai_service.extract_faces(query_path)
if not faces:
    print('No face in selfie.')
    exit(1)

query = faces[0]['embedding']
norm = np.linalg.norm(query)

with open('search_results.txt', 'w') as f:
    f.write(f'Index total vectors: {vector_store.index.ntotal}\n')
    f.write(f'Query vector norm: {norm:.4f}\n')
    matches = vector_store.search([query], top_k=5, threshold=1000.0, min_support=1)
    f.write(f'\nTop Matches found ({len(matches)}):\n')
    for m in matches:
        f.write(f"Path: {m['image_path']}, Score: {m['confidence']:.4f}\n")
