#===--rag_pipeline.py-----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import os
import sys
import chromadb
from chromadb.config import Settings
from pathlib import Path
from sentence_transformers import SentenceTransformer
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from handlers.logger import write_log

current_script_dir = Path(__file__).parent
model_path = current_script_dir.parent.parent / "models"
os.makedirs(model_path, exist_ok=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
documents_dir = os.path.join(script_dir, '..', '..', 'documents')
chroma_path = os.path.join(script_dir, '..', 'chroma')
docs_path = Path(documents_dir).resolve()

# Create the documents directory if it doesn't exist
os.makedirs(docs_path, exist_ok=True)

def init():
    emb_model = SentenceTransformer(str(model_path))
    client = chromadb.PersistentClient(chroma_path, settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(name="vectordb")
    return emb_model, client, collection

def create_documents(docs_path):
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"The directory {docs_path} does not exist. Please check the path.")

    book_files = [f for f in os.listdir(docs_path) if f.endswith(".pdf")]
    
    documents = []
    for book_file in book_files:
        file_path = os.path.join(docs_path, book_file)
        loader = PyPDFLoader(file_path)
        book_docs = loader.load()
        for doc in book_docs:
            doc.metadata = {"source": book_file}
            documents.append(doc)

    text_splitter = CharacterTextSplitter(chunk_size=1200, chunk_overlap=10, separator='\n')
    docs = text_splitter.split_documents(documents)
    return docs

def query_vector_store(query, emb_model, collection, k=1):
    query_embedding = emb_model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=k)
    extracted = ""

    if results["documents"] and results["documents"][0]:
        for result_doc in results["documents"][0]:
            extracted += result_doc + " "
    return extracted.strip()

def update_vector_store(docs, emb_model, collection):
    for i, doc in enumerate(docs):
        page_content = doc.page_content
        embeddings = emb_model.encode(page_content).tolist()
        
        source_id = doc.metadata.get("source", "unknown_source")
        unique_id = f"{source_id}_chunk_{i}"
        
        collection.add(documents=page_content, embeddings=embeddings, ids=[unique_id])

def delete_vector_store(client):
    collections = client.list_collections()
    if not collections:
        print("No collections found to delete.")
        return

    print("Deleting all existing ChromaDB collections...")
    for col in collections:
        client.delete_collection(col.name)
        print(f"Deleted collection: {col.name}")
    print("All collections deleted.")

def debug(collection):
    print(f"Collection Name: {collection.name}")
    print(f"Collection Count: {collection.count()}")
    results = collection.get()
    print("IDs:", results["ids"])
    # Print only the first few documents for brevity if many exist
    for i, result in enumerate(results["documents"]):
        if i < 5: # Limit to first 5 documents for debugging output
            print(f"Document {i+1}: {result[:100]}...") # Print first 100 chars
        else:
            print(f"({len(results['documents']) - i} more documents not shown)")
            break

def rag_pipeline(query):
    write_log(f"Query received: {query}")
    emb_model, client, collection = init()

    if query == "updateDB":
        delete_vector_store(client) 
        collection = client.get_or_create_collection(name="vectordb")
        
        print("Creating documents and updating vector store...")
        docs = create_documents(docs_path)
        if docs:
            update_vector_store(docs, emb_model, collection)
            print(f"Vector store updated with {collection.count()} documents.")
        else:
            print("No PDF documents found or created, vector store remains empty.")
    elif query == "@debugRAG":
        debug(collection)
    else:
        if collection.count() == 0:
            print("Vector store is empty. Please run 'updateDB' first.")
            write_log("Query attempted on empty vector store")
            return "No documents found in the knowledge base. Please upload documents and run 'updateDB' first."
        retrieved_context = query_vector_store(query, emb_model, collection)
        if not retrieved_context:
            write_log("No relevant context found for query")
            return "No relevant information found in the knowledge base for this query."
        return retrieved_context


def main(query):
    retrieved_context = rag_pipeline(query)

    if retrieved_context:
        print("\nRetrieved Context:")
        print(retrieved_context)
    elif retrieved_context is None and query not in ["updateDB", "@debugRAG"]:
        print("No context retrieved for the query.")
    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rag_pipeline.py <query_string>")
        print("Available commands: 'updateDB', '@debugRAG', or any natural language query.")
        sys.exit(1)
    
    main(query=sys.argv[1])
