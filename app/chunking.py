from langchain_text_splitters import RecursiveCharacterTextSplitter



def create_text_chunks(text):

    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 100,
    chunk_overlap = 50,
    )
    chunk = text_splitter.split_text(text)

    return chunk


test_text = "Apple reported strong quarterly financial results, with revenue increasing significantly compared with the same period last year."

chunks = create_text_chunks(test_text)

print(chunks)