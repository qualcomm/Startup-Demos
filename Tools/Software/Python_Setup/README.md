# Python Setup

## Table of Contents
- [Overview](#1-overview)
- [Windows Installation](#2-windows-installation)
- [Linux Installation](#3-linux-installation)
- [Virtual Environments](#4-virtual-environments)

## 1. Overview
Python is a high-level, interpreted programming language known for its readability and versatility. It's widely used in various domains including web development, data science, artificial intelligence, scientific computing, automation, and more. This guide provides instructions for setting up Python development environments on Windows and Linux platforms.

## 2. Windows Installation

### 2.1 Download Python Installer
1. Visit the official Python website: [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
2. Download the latest Python installer (e.g., Python 3.11.x)
3. Choose the appropriate installer:
   - Windows installer (64-bit) for 64-bit Windows
   - Windows installer (ARM64) for 64-bit Windows on ARM architecture
   - Windows installer (32-bit) for 32-bit Windows

### 2.2 Run the Installer
1. Launch the downloaded installer
2. Check "Add Python to PATH" (important for command-line access)
3. Click "Install Now" for standard installation or "Customize installation" for advanced options
4. Wait for the installation to complete

### 2.3 Verify Installation
1. Open Command Prompt (cmd)
2. Type `python --version` and press Enter
3. You should see the Python version displayed (e.g., "Python 3.11.x")
4. Type `pip --version` to verify pip installation

### 2.4 Install Python with Windows Package Manager (Alternative)
If you have Windows Package Manager (winget) installed:
```
winget install Python.Python.3.11
```

## 3. Linux Installation

### 3.1 Ubuntu/Debian
Most Linux distributions come with Python pre-installed. To install the latest version:

```bash
# Update package lists
sudo apt update

# Install Python
sudo apt install python3 python3-pip

# Verify installation
python3 --version
pip3 --version
```

## 4. Virtual Environments
Virtual environments are isolated Python environments that allow you to work on different projects with different dependencies without conflicts.

### 4.1 Creating Virtual Environments (Windows & Linux)
Using venv (built into Python 3.3+):

```bash
# Windows
python -m venv myenv
myenv\Scripts\activate

# Linux
python3 -m venv myenv
source myenv/bin/activate

# Deactivate (both platforms)
deactivate
