#===--ChatApp.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
from LLM_Utils.LLM_Handler import LLM_Module
from LLM_Utils.prompts import HISTORY_PROMPTS
import json

Response_Config = {
	"Short": 100,"Medium": 1000,"Large": 2500,
}
    
def main():
    # Page configuration
    st.set_page_config(
        page_title="History Teller",
        layout="wide"
    )

    # Header
    st.title("History Teller")
    st.markdown("*Made for Echonomical thinkers, for the nation studies*")

    
    with st.sidebar:
        # Add link to prompt editor
        st.markdown("### Tools")
        st.page_link("pages/prompt_editor.py", label="📝 Prompt Editor", icon="✏️")
        
        st.markdown("---")
        st.header("Development Aspects")
        development_aspects = st.multiselect(
            "Add Options",
            ["Human Resources", "Natural Resources", "Capital Formation", "Technological Innovation", "Political Stability", "Infrastructure", "Economic Policies",  "Social Factors", "Global Integration", "Environmental Sustainability"]
        )
        
        st.markdown("---")
        
        
        objectives = st.text_area("Focus",
            placeholder="Enter key area of interest")

    # Main content area with cleaner layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Parameters")
        year = st.selectbox("Year Range", ["1900-1920", "1920-1940", "1940-1960", "1960-1980", "1980-2000",
             "2000-2020", "2020-till date"])
        
        region = st.selectbox("Region",
            ["Africa", "Asia", "Europe", "North America", "South America", "Oceania", "Antarctica"])
        
        language = st.selectbox("Language",
            ["English", "Spanish", "French", "German", "Italian", "Portuguese", "Hindi", 
             "Chinese (Simplified)", "Japanese", "Korean"])

    with col2:
        st.subheader("Mode")
        mode = st.radio("Select",
            ["Political History", "Social History", "Economic History", "Cultural History"])
        
        response_length = st.select_slider("Response Length",
            options=Response_Config.keys(),
            value="Medium")
        
    # Initialize session
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    
    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""
        
    
    user_input = st.text_area(
        "Type your Query",
        value=st.session_state.user_input,
        height=100,
        placeholder="Enter Query",
        max_chars=1000,
        key="input_area"
    )
    
    # Initialize LLM
    llm = LLM_Module()
    
    if st.button("📚 Generate Response"):
        if not user_input.strip():
            st.error("Please enter a question or topic first!")
            return
        
        prompt = HISTORY_PROMPTS[mode].format(
            Year=year,
            region=region,
            topic=user_input,
            language=language
        )

        # Generate response
        response_placeholder = st.empty()
        full_response = ""
        
        with st.spinner(" Thinking..."):
            
            try:
                
                response_stream = llm.generate(
                    prompt=prompt,
                    add_ons=development_aspects if development_aspects else None,
                    additional_context=objectives if objectives else None,
                    resp_len = Response_Config[response_length] if response_length else None
                )
                
                # Process the stream
                for chunk in response_stream:
                    if chunk:
                        try:
                            # Parse the chunk
                            chunk_data = json.loads(chunk.decode('utf-8').strip('data: ').strip())
                            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                content = chunk_data['choices'][0].get('delta', {}).get('content', '')
                                if content:
                                    full_response += content
                                    # Update the response in real-time
                                    response_placeholder.markdown(full_response + "▌")
                        except json.JSONDecodeError:
                            continue
                response_placeholder.markdown(full_response)
                st.session_state.conversation_history.append((user_input, full_response))
                
                st.session_state.user_input = ""
                st.experimental_rerun()
                
            except Exception as e:
                st.error(f"Error generating response: {str(e)}")
    
    # Conversation history
    if st.session_state.conversation_history:
        st.markdown("### History")
        print(st.session_state.conversation_history)
        for i, (question, answer) in enumerate(reversed(st.session_state.conversation_history)):
            msg_num = len(st.session_state.conversation_history) - i
            
            st.markdown(f"**Q{msg_num}:**")
            st.markdown(f"```\n{question}\n```")
            
            st.markdown(f"**A{msg_num}:**")
            st.markdown(answer)
                        
            st.markdown("---")

if __name__ == "__main__":
    main()
