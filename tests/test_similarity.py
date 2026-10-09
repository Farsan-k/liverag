
import numpy as np

from app.embeddings import generate_embedding


sentence_a = "Apple reported strong quarterly revenue growth."
sentence_b = "Apple's sales increased significantly this quarter."
sentence_c = "The weather will be sunny tomorrow."

embedding_a = generate_embedding(sentence_a)
embedding_b = generate_embedding(sentence_b)
embedding_c = generate_embedding(sentence_c)


def cosine_similarity(vector_a, vector_b):
    a = np.array(vector_a)
    b = np.array(vector_b)

    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )


similarity_ab = cosine_similarity(embedding_a, embedding_b)
similarity_ac = cosine_similarity(embedding_a, embedding_c)

print(f"Apple sentences similarity: {similarity_ab:.4f}")
print(f"Apple vs weather similarity: {similarity_ac:.4f}")
