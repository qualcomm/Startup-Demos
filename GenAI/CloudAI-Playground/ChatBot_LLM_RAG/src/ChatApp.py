#===--ChatApp.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from LLM_Utils.LLM_Handler import LLM_Module
from LLM_Utils.PDF_Handler import PDF_Module
from LLM_Utils.EMB_Handler import EMB_Module
from LLM_Utils.ConversationHandler import ConvHistory_Module
from LLM_Utils.PromptHandler import PromptHandler

import streamlit as st
import os
from datetime import datetime

class LLMChatApp:
    def __init__(self):
        self.Interface_List = {
            'Cloud AI Playground(AIsuite)': 'https://aisuite.cirrascale.com/apis/v2',
            'ALLaM Developer Playground': 'https://allam-playground.com/apis/v2',
            'Cloud AI Playground': 'https://cloudai.cirrascale.com/apis/v2',
            'Custom': 'https://cloudai.cirrascale.com/apis/v2'
        }
        self.session_state = {
            'API_END_POINT_LLM': "",
            'API_END_POINT_EMB': "",
            'API_KEY_LLM': "",
            'API_KEY_EMB': "",
            'user_input': "",
            'use_embeddings': False,
            'conversation_history': ConvHistory_Module(),
            'prompt_handler': PromptHandler(),
            'pdf_reader': PDF_Module(),
            'llm': None,
            'emb': None,
            'show_download': False
        }
        self.intermediates = {
            'paragraphs': None
        }

    def get_llm(self):
        if 'llm' in self.session_state:
            return self.session_state['llm']
        else:
            return None

    def get_emb(self):
        if 'emb' in self.session_state:
            return self.session_state['emb']
        else:
            return None

    def get_conv_history(self):
        if 'conversation_history' in self.session_state:
            return self.session_state['conversation_history']
        else:
            return None

    def get_prompt_handler(self):
        if 'prompt_handler' in self.session_state:
            return self.session_state['prompt_handler']
        else:
            return None

    def get_pdf_reader(self):
        if 'pdf_reader' in self.session_state:
            return self.session_state['pdf_reader']
        else:
            return None

    def page_config(self):
        st.set_page_config(
            page_title="Cloud AI100 Playground",
            layout="wide"
        )
        st.write("Last Refreshed: " + datetime.now().time().strftime("%H:%M:%S"))

    def header(self):
        st.title("Playground Chat + RAG + ChromaDB Demo")

    def configure_llm(self):
        st.sidebar.title("Configure LLM")

        SelectedInterface_LLM = st.sidebar.selectbox(
            "Select the LLM Instance",
                list(self.Interface_List.keys())
        )
        if SelectedInterface_LLM == 'Custom':
            self.Interface_List[SelectedInterface_LLM] = st.sidebar.text_input(
                "Configure your endpoint",
                self.Interface_List[SelectedInterface_LLM],
                key="llm_endpoint"
            )
        API_END_POINT_LLM = self.Interface_List[SelectedInterface_LLM]

        API_KEY_LLM = st.sidebar.text_input(
            "Configure your API Key for " + SelectedInterface_LLM,
            os.getenv("LLM_API_KEY", ""),
            key="llm_apikey",type="password"
        )

        if self.session_state['API_END_POINT_LLM'] != API_END_POINT_LLM or \
           self.session_state['API_KEY_LLM'] != API_KEY_LLM:
            
            self.session_state['API_END_POINT_LLM'] = API_END_POINT_LLM
            self.session_state['API_KEY_LLM'] = API_KEY_LLM

            if 'llm' in self.session_state:
                del self.session_state['llm']

        if API_KEY_LLM != "" and API_END_POINT_LLM != "":
            # Initialize LLM
            if 'llm' not in self.session_state:
                self.session_state['llm'] = LLM_Module(
                endpoint=API_END_POINT_LLM,
                api_key=API_KEY_LLM
            )
            llm = self.session_state['llm']
            SelectedLLMModel = st.sidebar.selectbox(
                "Select the LLM Model",
                llm.get_models()
            )
            llm.set_model(SelectedLLMModel)

    def configure_emb(self):
        SelectedInterface_EMB = st.sidebar.selectbox(
            "Select the Embedding Instance",
            list(['Same as above']) + list(self.Interface_List.keys())
            )
        if SelectedInterface_EMB == 'Custom':
            self.Interface_List[SelectedInterface_EMB] = st.sidebar.text_input(
                "Configure your endpoint",
                self.Interface_List[SelectedInterface_EMB],
                key="emb_endpoint"
        )
        if SelectedInterface_EMB != 'Same as above':
            API_END_POINT_EMB = self.Interface_List[SelectedInterface_EMB]
            API_KEY_EMB = st.sidebar.text_input(
                "Configure your API Key for " + SelectedInterface_EMB,
                key="emb_api_key",type="password"
            )
        else:
            API_END_POINT_EMB = self.session_state['API_END_POINT_LLM']
            API_KEY_EMB = self.session_state['API_KEY_LLM']

        if self.session_state['API_END_POINT_EMB'] != API_END_POINT_EMB or \
           self.session_state['API_KEY_EMB'] != API_KEY_EMB:

            self.session_state['API_END_POINT_EMB'] = API_END_POINT_EMB
            self.session_state['API_KEY_EMB'] = API_KEY_EMB
            if 'emb' in self.session_state:
                del self.session_state['emb']

        if API_KEY_EMB != "" and API_END_POINT_EMB != "":
            # Initialize Embeddings
            if 'emb' not in self.session_state:
                self.session_state['emb'] = EMB_Module(
                    endpoint=API_END_POINT_EMB,
                    api_key=API_KEY_EMB,
                    collection_name="pdf_file"
                )
            emb = self.session_state['emb']
            SelectedEMBModel = st.sidebar.selectbox(
                "Select the Embedding Model",
                emb.get_models()
                )
            emb.set_model(SelectedEMBModel)

    def file_uploader(self):
        uploaded_file = st.file_uploader("Upload the PDF file for Embedding and RAG", type="pdf")
        if uploaded_file is not None:
            pdf_reader = self.session_state['pdf_reader']
            self.intermediates['paragraphs'] = pdf_reader.generate(uploaded_pdf_file=uploaded_file)

    def database_buttons(self):
        emb = self.get_emb()
        if emb is not None:
            check_db = emb.check_db()
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            use_embeddings = self.session_state['use_embeddings']
            paragraphs = self.intermediates['paragraphs']
            with col1:
                if st.button("Use Existing Data Base", key='col_main1'):
                    use_embeddings = check_db and True or False
            with col2:
                if st.button("Add to Existing Data Base", key='col_main2'):
                    if paragraphs is not None:
                        emb.generate(paragraphs)
                        use_embeddings = True
            with col3:
                if st.button("Generate New Data Base", key='col_main3'):
                    if paragraphs is not None:
                        if check_db == True:
                            self.get_emb().clear_db()
                        emb.generate(paragraphs)
                        use_embeddings = True
            with col4:
                if st.button("Clear Data Base", key='col_main4'):
                    if check_db == True:
                        emb.clear_db()
                        use_embeddings = False
            with col5:
                if st.button("No Database", key='col_main5'):
                    use_embeddings = False
            with col6:
                if st.button("Clear Chat History", key='col_main6'):
                    self.get_conv_history().clear_history()
            
            self.session_state['use_embeddings'] = use_embeddings
        

    def generate_response(self):
        user_input = st.text_area(
            "Type your Query",
            value="",
            height=50,
            max_chars=1000,
            key="input_area"
        )
        if st.button("📚 Generate Response"):
            if not user_input.strip():
                st.error("Please enter a question or topic first!")
                return
            prompt = user_input
            # Generate response
            response_placeholder = st.empty()
            full_response = ""
            self.session_state['show_download'] = False
            with st.spinner("🤖 Thinking..."):
                try:
                    # Use PromptHandler to generate prompt
                    generated_prompt = self.session_state['prompt_handler'].generate_prompt(
                        user_input=prompt,
                        context=self.session_state['emb'].retrieve(query=prompt) if self.session_state['use_embeddings'] else None,
                        conversation_history=self.session_state['conversation_history'].get_complete_conversation_history()
                    )
                    response_stream = self.session_state['llm'].generate(
                        prompt=generated_prompt
                    )
                    full_response = response_stream
                    response_placeholder.markdown(full_response)
                    self.session_state['conversation_history'].update_conversation_history(user_input, full_response)
                    self.session_state['user_input'] = ""
                except Exception as e:
                    st.error(f"Error generating response: {str(e)}")

    def print_history(self):
        self.session_state['conversation_history'].print_history()

def main():
    if 'ChatApp' not in st.session_state:
        st.session_state.ChatApp = LLMChatApp()
        st.rerun()
    else:
        ChatApp = st.session_state['ChatApp']
        ChatApp.page_config()
        ChatApp.header()
        ChatApp.configure_llm()
        ChatApp.configure_emb()
        ChatApp.file_uploader()
        ChatApp.database_buttons()
        ChatApp.generate_response()
        ChatApp.print_history()

if __name__ == "__main__":
    main()