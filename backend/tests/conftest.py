"""
Stubs out all external services (Pinecone, OpenRouter, pypdf) via sys.modules
injection before any app code is imported. No real API keys or network needed.
"""
import sys
import os
from unittest.mock import MagicMock

# Make app/ importable when running pytest from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

# Build a fake settings object
_mock_settings = MagicMock()
_mock_settings.OPENROUTER_API_KEY = "test-key"
_mock_settings.PINECONE_API_KEY = "test-key"
_mock_settings.PINECONE_INDEX_NAME = "test-index"
_mock_settings.APP_NAME = "AIDA"
_mock_settings.APP_VERSION = "0.1.0"
_mock_settings.CORS_ORIGINS = ["http://localhost:5173"]

_core_config_stub = MagicMock()
_core_config_stub.settings = _mock_settings

# Inject stubs before any app module is first imported
sys.modules.setdefault("core.config", _core_config_stub)
sys.modules.setdefault("openrouter", MagicMock())
sys.modules.setdefault("pinecone", MagicMock())
sys.modules.setdefault("pypdf", MagicMock())
