
from app.hashing import calculate_content_hash


def main():
    original_text = "Revenue increased by 10%."
    unchanged_text = "Revenue increased by 10%."
    updated_text = "Revenue increased by 20%."

    original_hash = calculate_content_hash(original_text)
    unchanged_hash = calculate_content_hash(unchanged_text)
    updated_hash = calculate_content_hash(updated_text)

    print("Original hash:", original_hash)
    print("Unchanged hash:", unchanged_hash)
    print("Updated hash:", updated_hash)

    assert original_hash == unchanged_hash
    assert original_hash != updated_hash

    print("Content hashing test passed!")


if __name__ == "__main__":
    main()
