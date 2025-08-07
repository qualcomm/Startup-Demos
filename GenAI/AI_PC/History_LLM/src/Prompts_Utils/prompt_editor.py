#===--prompt_editor.py----------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
import os
import sys
import json
import copy
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLM_Utils.prompts import HISTORY_PROMPTS

st.set_page_config(page_title="Prompt Editor", layout="wide")
st.title("Prompt Template Editor")
st.markdown("Edit and configure the prompt templates used by the History Teller application")

if 'original_prompts' not in st.session_state:
    st.session_state.original_prompts = copy.deepcopy(HISTORY_PROMPTS)
    
if 'current_prompts' not in st.session_state:
    st.session_state.current_prompts = copy.deepcopy(HISTORY_PROMPTS)

if 'test_values' not in st.session_state:
    st.session_state.test_values = {
        'topic': 'Industrial Revolution',
        'region': 'Europe',
        'Year': '1800-1900',
        'language': 'English'
    }

def format_prompts_as_python(prompts):
    lines = ["HISTORY_PROMPTS = {"]
    
    for i, (key, value) in enumerate(prompts.items()):
        if i > 0:
            lines.append("")
        lines.append(f'    "{key}": """{value}')
        
        if i < len(prompts) - 1:
            lines.append('    """,')
        else:
            lines.append('    """')
    
    lines.append("}")
    return "\n".join(lines)

def save_prompts(updated_prompts):
    try:
        # Get the path to the prompts.py file
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_file_path = os.path.join(current_dir, "LLM_Utils", "prompts.py")
        
        # Create a backup of the original file
        backup_path = prompts_file_path + ".backup"
        with open(prompts_file_path, 'r') as f:
            original_content = f.read()
        
        with open(backup_path, 'w') as f:
            f.write(original_content)
        
        # Format the updated prompts as Python code
        formatted_prompts = format_prompts_as_python(updated_prompts)
        
        # Write the updated prompts to the file
        with open(prompts_file_path, 'w') as f:
            f.write(formatted_prompts)
        
        return True, "Prompts saved successfully! A backup was created at " + backup_path
    except Exception as e:
        return False, f"Error saving prompts: {str(e)}"

# Function to preview a prompt with test values
def preview_prompt(prompt_template, test_values):
    try:
        return prompt_template.format(**test_values)
    except KeyError as e:
        return f"Error: Missing key {str(e)} in test values"
    except Exception as e:
        return f"Error formatting prompt: {str(e)}"

with st.sidebar:
    st.header("Test Values")
    st.markdown("These values will be used to preview the prompts")
    
    st.session_state.test_values['topic'] = st.text_input(
        "Topic", 
        value=st.session_state.test_values['topic']
    )
    
    st.session_state.test_values['region'] = st.text_input(
        "Region", 
        value=st.session_state.test_values['region']
    )
    
    st.session_state.test_values['Year'] = st.text_input(
        "Year", 
        value=st.session_state.test_values['Year']
    )
    
    st.session_state.test_values['language'] = st.text_input(
        "Language", 
        value=st.session_state.test_values['language']
    )
    
    # Reset all prompts button
    if st.button("Reset All Prompts to Original"):
        st.session_state.current_prompts = copy.deepcopy(st.session_state.original_prompts)
        st.success("All prompts have been reset to their original values")

# Main content - Tabs for each prompt type
tab1, tab2, tab3, tab4 = st.tabs([
    "Political History", 
    "Social History", 
    "Economic History", 
    "Cultural History"
])

with tab1:
    st.header("Political History Prompt")
    
    political_prompt = st.text_area(
        "Edit the prompt template",
        value=st.session_state.current_prompts["Political History"],
        height=400
    )
    
    st.session_state.current_prompts["Political History"] = political_prompt
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Preview Political History Prompt"):
            st.subheader("Preview:")
            preview = preview_prompt(political_prompt, st.session_state.test_values)
            st.text_area("Formatted Prompt", value=preview, height=300, disabled=True)
    
    with col2:
        if st.button("Reset Political History Prompt"):
            st.session_state.current_prompts["Political History"] = st.session_state.original_prompts["Political History"]
            st.success("Political History prompt has been reset to original")
            st.experimental_rerun()

with tab2:
    st.header("Social History Prompt")
    
    social_prompt = st.text_area(
        "Edit the prompt template",
        value=st.session_state.current_prompts["Social History"],
        height=400
    )
    
    st.session_state.current_prompts["Social History"] = social_prompt
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Preview Social History Prompt"):
            st.subheader("Preview:")
            preview = preview_prompt(social_prompt, st.session_state.test_values)
            st.text_area("Formatted Prompt", value=preview, height=300, disabled=True)
    
    with col2:
        if st.button("Reset Social History Prompt"):
            st.session_state.current_prompts["Social History"] = st.session_state.original_prompts["Social History"]
            st.success("Social History prompt has been reset to original")
            st.experimental_rerun()

with tab3:
    st.header("Economic History Prompt")
    
    economic_prompt = st.text_area(
        "Edit the prompt template",
        value=st.session_state.current_prompts["Economic History"],
        height=400
    )
    
    st.session_state.current_prompts["Economic History"] = economic_prompt
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Preview Economic History Prompt"):
            st.subheader("Preview:")
            preview = preview_prompt(economic_prompt, st.session_state.test_values)
            st.text_area("Formatted Prompt", value=preview, height=300, disabled=True)
    
    with col2:
        if st.button("Reset Economic History Prompt"):
            st.session_state.current_prompts["Economic History"] = st.session_state.original_prompts["Economic History"]
            st.success("Economic History prompt has been reset to original")
            st.experimental_rerun()

with tab4:
    st.header("Cultural History Prompt")
    
    cultural_prompt = st.text_area(
        "Edit the prompt template",
        value=st.session_state.current_prompts["Cultural History"],
        height=400
    )
    
    st.session_state.current_prompts["Cultural History"] = cultural_prompt
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Preview Cultural History Prompt"):
            st.subheader("Preview:")
            preview = preview_prompt(cultural_prompt, st.session_state.test_values)
            st.text_area("Formatted Prompt", value=preview, height=300, disabled=True)
    
    with col2:
        if st.button("Reset Cultural History Prompt"):
            st.session_state.current_prompts["Cultural History"] = st.session_state.original_prompts["Cultural History"]
            st.success("Cultural History prompt has been reset to original")
            st.experimental_rerun()

st.markdown("---")
if st.button("Save All Prompts", type="primary"):
    success, message = save_prompts(st.session_state.current_prompts)
    if success:
        st.success(message)
    else:
        st.error(message)

with st.expander("Help & Instructions"):
    st.markdown("""
    ## How to use the Prompt Editor
    
    1. **Edit Prompts**: Use the tabs to navigate between different prompt types and edit them in the text areas.
    2. **Preview**: Click the "Preview" button to see how the prompt looks with the test values.
    3. **Reset**: Use the "Reset" button to revert a specific prompt to its original value.
    4. **Save**: Click "Save All Prompts" to save your changes to the prompts.py file.
    
    ### Template Variables
    
    The following variables are available in the prompt templates:
    
    - `{topic}`: The topic of the history query
    - `{region}`: The geographical region
    - `{Year}`: The time period
    - `{language}`: The language for the response
    
    ### Tips
    
    - Always preview your changes before saving to ensure the prompt is formatted correctly.
    - A backup of the original prompts.py file is created when you save changes.
    - You can reset all prompts to their original values using the button in the sidebar.
    """)
