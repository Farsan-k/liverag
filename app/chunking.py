
from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_text_chunks(text, document_id):

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=100,
        chunk_overlap=50,
    )

    chunks = text_splitter.split_text(text)

    chunk_list = []

    for chunk_index, tex in enumerate(chunks):
        chunk_dict = {
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": tex,
        }

        chunk_list.append(chunk_dict)

    return chunk_list
