#===--PromptHandler.py----------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

class PromptHandler:
    def __init__(self):
        self.system_prompts = [
            "You are a helpful assistant. Respond to user queries across a wide range of topics. Be clear, accurate, and informative. If the query is unclear or you do not know the answer, do not guess—say 'I do not know' or ask the user for more information.",
            "You are a helpful assistant. Use the conversation history provided in the user's query to understand and answer the question. If the context is missing or the query is unclear, do not guess—say 'I do not know' or ask the user for clarification.",
            "You are a helpful assistant. Use the context provided from the retrieval-augmented generation (RAG) system to answer the user's query. If the context does not contain the answer or the query is unclear, do not guess—say 'I do not know' or ask the user for more information.",
            "You are a helpful assistant. Use both the conversation history provided in the user's query and the context from the retrieval-augmented generation (RAG) system to answer the question. If the answer is not present or the query is ambiguous, do not guess—respond with 'I do not know' or ask the user for clarification."
        ]
        self.prompt = None

    def get_system_prompts(self):
        return self.system_prompts

    def append_system_prompt(self, new_prompt):
        self.system_prompts.append(new_prompt)

    def get_system_prompt_index(self, system_prompt):
        try:
            return self.system_prompts.index(system_prompt)
        except ValueError:
            return -1

    def select_system_prompt(self, context=None, conversation_history=None, index=None):
        if index is not None:
            if 0 <= index < len(self.system_prompts):
                return self.system_prompts[index]
            else:
                return self.system_prompts[0]
        elif context is not None or conversation_history is not None:
            if context is not None and conversation_history is not None:
                return self.system_prompts[3]
            elif context is not None:
                return self.system_prompts[2]
            elif conversation_history is not None:
                return self.system_prompts[1]
        else:
            return self.system_prompts[0]

    def get_top_n_conversations(self, conversation_history, n=0, max_chars=100):
        def truncate_string(s, max_chars):
            if len(s) > max_chars:
                return s[:max_chars] + "..."
            else:
                return s

        top_n_conversations = conversation_history[-n:]
        truncated_conversations = []
        for conversation in top_n_conversations:
            user_input, full_response = conversation
            truncated_user_input = truncate_string(user_input, max_chars)
            truncated_full_response = truncate_string(full_response, max_chars)
            truncated_conversation = f"User: {truncated_user_input}\nAssistant: {truncated_full_response}"
            truncated_conversations.append(truncated_conversation)

        top_n_conversations_str = "\n".join(truncated_conversations)
        return top_n_conversations_str

    def generate_prompt(self, user_input, context=None, conversation_history=None, n=0, **kwargs):
        if not self.system_prompts:
            raise ValueError("System prompts list is empty. Please use get_system_prompts method to create a list of system prompts.")
        
        system_prompt = self.select_system_prompt(context, conversation_history)
        if user_input is None or user_input.strip() == "":
            user_query = "No user input provided."
        else:
            user_query = f"{user_input}"
            if context is not None:
                user_query += f"\nContext: {context}"
            if conversation_history is not None:
                top_n_conversations = self.get_top_n_conversations(conversation_history, n, 100)
                user_query += f"\nTop {n} Conversations: {top_n_conversations}"
        for key, value in kwargs.items():
            user_query = user_query.replace(f"{{{key}}}", str(value))
        message = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_query}
        ]
        self.prompt = message
        return self.prompt
