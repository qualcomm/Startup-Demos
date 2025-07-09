#===--EMB_Handler.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from openai import OpenAI
from dotenv import load_dotenv
import chromadb 
from chromadb.utils import embedding_functions
import httpx

class EMB_Module:
    def __init__(self, endpoint, api_key, model="BAAI/bge-large-en-v1.5", collection_name="default"):
        self.api_endpoint = endpoint
        self.api_key = api_key
        self.model_name = model
        self.collection_name = collection_name
        self.timeout = 60
        self.openai_client = None
        self.embedding_function = None
        try:
            self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        except:
            raise Exception(
                "Chroma Client Initialization Failure"
            )

    def get_embedding_fn(self) -> OpenAI:
        if not self.embedding_function:
            self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.api_key,
                model_name=self.model_name,
                api_base=self.api_endpoint,
            )
            self.embedding_function._client = \
                self.openai_client.embeddings
        return self.embedding_function
    
    def get_client(self) -> OpenAI:
        if not self.openai_client:
            self.openai_client = OpenAI(
                base_url=self.api_endpoint,
                api_key=self.api_key,
                http_client=httpx.Client(verify=False)
            )
        return self.openai_client

    def get_models(self, paragraphs=None):
        try:
            openai_client = self.get_client()
            models = openai_client.models.list()
            return models.embedding
        except Exception as e:
            raise Exception("EMB_Module: Get Models Failed!")

    def generate(self, paragraphs):
        try:
            embedding_function = self.get_embedding_fn()
            
            chroma_client = self.chroma_client
            
            collection = chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space" : "cosine"}
            )
            start_idx = collection.count()
            for idx, paragraph in enumerate(paragraphs):
                collection.add(documents=[paragraph.page_content], ids=[f"paragraph_{start_idx + idx}"])
            print(f"Stored {len(paragraphs)} paragraphs in ChromaDB.")
            
        except:
            raise Exception(
                "LLM Connection Failure"
                f"at {self.api_endpoint} Initiate Retry."
            )
    
    def set_model(self, model="BAAI/bge-large-en-v1.5"):
        self.model_name = model
            
    def retrieve(self, query):
        try:
            embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.api_key,
                model_name=self.model_name,
                api_base=self.api_endpoint,
            )
            
            openai_client = self.get_client()
            embedding_function._client = openai_client.embeddings
            
            chroma_client = self.chroma_client
            
            collection = chroma_client.get_collection(
                name=self.collection_name,
                embedding_function=embedding_function)
            
            results = collection.query(query_texts=[query], n_results=3)
        
        except:
            raise Exception(
                "LLM(EMB) Connection Failure"
                f"at {self.api_endpoint} Initiate Retry."
            )
            
        if results and results['documents']:
            return ''.join(results['documents'][0])
        return 'No relevant information found.'
     
    def clear_db(self):
        try:
            embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.api_key,
                model_name=self.model_name,
                api_base=self.api_endpoint,
            )
            
            openai_client = self.get_client()
            embedding_function._client = openai_client.embeddings
            
            chroma_client = self.chroma_client
            
            collection = chroma_client.delete_collection(
                name=self.collection_name)
                    
        except:
            raise Exception(
                "LLM Connection Failure"
                f"at {self.api_endpoint} Initiate Retry."
            )
     
    def check_db(self):
        try:
            embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                api_key=self.api_key,
                model_name=self.model_name,
                api_base=self.api_endpoint,
            )
            
            openai_client = self.get_client()
            embedding_function._client = openai_client.embeddings
            
            chroma_client = self.chroma_client
            
            collection = chroma_client.get_collection(
                name=self.collection_name,
                embedding_function=embedding_function)
            return True
                    
        except:
            return False
