#===--pdf_utils.py--------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

"""
PDF Reader module for extracting and chunking text into paragraphs.
"""
from typing import List
import fitz  # PyMuPDF
import os
from llm.config_manager import get_config_value

def read_pdf_paragraphs(pdf_path: str) -> List[str]:
    """
    Reads a PDF file and returns a list of paragraphs (chunks).
    Args:
        pdf_path: Path to the PDF file.
    Returns:
        List of paragraph strings.
    """
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    # Split into paragraphs (by double newlines or single newlines)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) == 1:
        # fallback: split by single newline if only one chunk
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return paragraphs
