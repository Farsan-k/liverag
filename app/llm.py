
import ollama


MODEL_NAME = "qwen2.5:3b"


def generate_answer(question: str, context: str) -> str:
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Finova AI, a financial intelligence assistant. "
                    "Answer using only the provided context. "
                    "If the context does not contain enough information, "
                    "clearly say you do not have enough information. "
                    "Do not invent financial facts."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question:\n{question}"
                ),
            },
        ],
    )

    return response["message"]["content"]
