
from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_text_chunks(text, document_id):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        add_start_index=False,
    )

    chunks = text_splitter.split_text(text)

    chunk_list = []

    for chunk_index, chunk_text in enumerate(chunks):
        chunk_list.append({
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": chunk_text,
        })

    return chunk_list
