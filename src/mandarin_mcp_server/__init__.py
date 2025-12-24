"""
Mandarin Learning MCP Server

MCP server for learning Mandarin Chinese vocabulary and phrases
from HSK levels 1-6, with progress tracking and exports for Anki.
"""

__version__ = "0.1.0"
__author__ = "Mihalis"

from .server import MandarinMCPServer, main

__all__ = ["MandarinMCPServer", "main", "__version__"]