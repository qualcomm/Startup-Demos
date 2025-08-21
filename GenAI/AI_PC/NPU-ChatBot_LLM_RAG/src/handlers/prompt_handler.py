#===--prompt_handler.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//
import sys
from langchain_core.prompts import PromptTemplate
from handlers.rag_pipeline import rag_pipeline as rag
from handlers.logger import write_log

LLM_BEGIN_TEXT_TOKEN = "<|begin_of_text|>"
LLM_END_TEXT_TOKEN = "<|eot_id|>"
LLM_SYSTEM_HEADER_START = "<|start_header_id|>system<|end_header_id|>"
LLM_USER_HEADER_START = "<|start_header_id|>user<|end_header_id|>"
LLM_CONTEXT_START = "<|start_context|>"
LLM_CONTEXT_END = "<|end_context|>"

RAG_PROMPT_TEMPLATE = f"{LLM_BEGIN_TEXT_TOKEN}{LLM_SYSTEM_HEADER_START}You are a helpful assistant. Be precise. If context is insufficient or not having specific info to the question, respond with I don't know. Strictly answer only from the following context:\n\n{{context}},\n\nQuestion: {{question}}\nAnswer: {LLM_END_TEXT_TOKEN}"

# Langchain PromptTemplate for RAG flow
rag_prompt_template_lc = PromptTemplate(
    input_variables=["context", "question"],
    template=RAG_PROMPT_TEMPLATE,
)

def prompt_handler(user_query: str, bot_name: str, rag_enabled: bool) -> str:
    """
    Constructs a prompt for the language model based on RAG status.

    Args:
        user_query (str): The user's input query.
        bot_name (str): The name of the chatbot.
        rag_enabled (bool): True if RAG (Retrieval Augmented Generation) is enabled, False otherwise.

    Returns:
        str: The fully formatted prompt for the language model.
    """
    if rag_enabled:
        # Use the predefined Langchain prompt template for RAG
        retrieved_context = str(rag(user_query))
        prompted_query = rag_prompt_template_lc.format(context=retrieved_context, question=user_query)
        write_log("RAG-enabled prompt prepared.")
        return prompted_query
    else:
        # Construct a non-RAG prompt
        system_prefix = f"{LLM_BEGIN_TEXT_TOKEN}{LLM_SYSTEM_HEADER_START}"
        system_message = f"Your name is {bot_name} and you are a helpful AI assistant. Please keep answers concise and to the point. {LLM_END_TEXT_TOKEN}\n\n"
        user_prompt = f"{LLM_USER_HEADER_START}\n\n{user_query}{LLM_END_TEXT_TOKEN}"
        write_log("simple assistant prompt prepared.")
        # Combine parts for the final prompt
        return f"{system_prefix}{system_message}{user_prompt}"

def main():
    """
    Main function to parse command-line arguments and generate a prompt.
    """
    if len(sys.argv) != 4:
        print("Usage: python prompt_handler.py <user_query> <bot_name> <RAG_status>")
        print("Example: python prompt_handler.py \"What is a CPU?\" \"QBot\" \"True\"")
        sys.exit(1)

    user_query = sys.argv[1]
    bot_name = sys.argv[2]
    rag_status_str = sys.argv[3].lower()
    rag_enabled = (rag_status_str == 'true' or rag_status_str == '1')

    # Validate rag_status_str if stricter input required
    if rag_status_str not in ['true', 'false', '1', '0']:
        print(f"Error: Invalid RAG_status '{sys.argv[3]}'. Expected 'True'/'False' or '1'/'0'.")
        sys.exit(1)

    generated_prompt = prompt_handler(user_query, bot_name, rag_enabled)
    print(generated_prompt)
    write_log(f"Generated prompt for user query: '{user_query}'")

if __name__ == "__main__":
    main()
