#===--app.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import streamlit as st
from modules.pages.workspace import workspace_page
from modules.pages.dashboard import dashboard_page

st.set_page_config(page_title="🎫 Ticket Counter", layout="wide")

st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to", ["Workspace", "Dashboard"])

if page == "Workspace":
    workspace_page()
elif page == "Dashboard":
    dashboard_page()

