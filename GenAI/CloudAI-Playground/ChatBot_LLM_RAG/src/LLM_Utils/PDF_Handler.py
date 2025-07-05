#===--PDF_Handler.py------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

class PDF_Module:
    def __init__(self):
        self.timeout = 60

    def generate(self, pdf_path=None, uploaded_pdf_file=None):
        try:
            if pdf_path != None:
                # Load the PDF file
                loader = PyPDFLoader(pdf_path)
                
            elif uploaded_pdf_file != None:
                
                with open(uploaded_pdf_file.name, mode='wb') as w:
                    w.write(uploaded_pdf_file.getvalue())
                    
                # Load and display the PDF content using PyPDFLoader
                loader = PyPDFLoader(uploaded_pdf_file.name)
                
            # Load the document
            document = loader.load()
            
            # Split the document into paragraphs
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
            return splitter.split_documents(document)
            
        except :
            raise Exception(
                "PDF Load Failure"
            )
