
from app.embeddings import generate_embedding


def test_generate_embedding():
    text = "Apple reported strong quarterly revenue growth."

    embedding = generate_embedding(text)

    print("Vector dimensions:", len(embedding))
    print("First five values:", embedding[:5])

    assert len(embedding) == 384
    assert all(isinstance(value, float) for value in embedding)

    print("Embedding test passed")


if __name__ == "__main__":
    test_generate_embedding()
