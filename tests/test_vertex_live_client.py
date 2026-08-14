"""Unit tests for Vertex AI Live API client, ADC token acquisition, and model path construction."""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.core.live_gemini_client import (
    GeminiLiveSession,
    get_vertex_access_token,
    get_vertex_live_ws_url,
    get_genai_client,
)


class TestVertexLiveClient(unittest.IsolatedAsyncioTestCase):

    def test_vertex_ws_url_formatting(self):
        """Verify Vertex AI regional WebSocket URL construction."""
        url_us = get_vertex_live_ws_url("us-central1")
        self.assertEqual(
            url_us,
            "wss://us-central1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
        )

        url_asia = get_vertex_live_ws_url("asia-south1")
        self.assertEqual(
            url_asia,
            "wss://asia-south1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
        )

    def test_vertex_access_token_mock(self):
        """Verify Vertex AI ADC token retrieval using Google Auth."""
        mock_credentials = MagicMock()
        mock_credentials.token = "mock_oauth2_token_xyz"
        mock_auth = MagicMock()
        mock_auth.default.return_value = (mock_credentials, "1047195478355")
        mock_requests = MagicMock()

        mock_google = MagicMock()
        mock_google.auth = mock_auth
        mock_google.auth.transport = MagicMock()
        mock_google.auth.transport.requests = mock_requests

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.auth": mock_auth,
            "google.auth.transport": mock_google.auth.transport,
            "google.auth.transport.requests": mock_requests
        }):
            token = get_vertex_access_token()
            self.assertEqual(token, "mock_oauth2_token_xyz")

    def test_vertex_access_token_fallback(self):
        """Verify graceful None return when Google Auth is not available."""
        with patch.dict("sys.modules", {"google.auth": None, "google.auth.transport.requests": None}):
            token = get_vertex_access_token()
            self.assertIsNone(token)

    async def test_session_start_and_utterance(self):
        """Verify dynamic GeminiLiveSession initialization and conversational handling."""
        session = GeminiLiveSession(
            customer_id="CUST-101",
            profile_data={"customer": {"full_name": "Ramesh Sharma"}}
        )
        await session.start()
        self.assertTrue(session._running)
        self.assertEqual(session._model_name, "gemini-live-2.5-flash-native-audio")
        await session.close()
        self.assertFalse(session._running)

    def test_get_genai_client_init(self):
        """Verify get_genai_client creates Client with vertexai=True, project, and location."""
        mock_client_instance = MagicMock()
        with patch("backend.app.core.live_gemini_client.genai.Client", return_value=mock_client_instance) as mock_cls:
            client = get_genai_client()
            self.assertEqual(client, mock_client_instance)
            mock_cls.assert_called_once_with(
                vertexai=True,
                project=settings.GCP_PROJECT_ID,
                location=settings.GCP_LOCATION
            )

    def test_vertex_access_token_cached_valid(self):
        """Verify existing valid token is returned without redundant refresh."""
        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials.token = "mock_cached_valid_token"
        mock_auth = MagicMock()
        mock_auth.default.return_value = (mock_credentials, "1047195478355")
        mock_requests = MagicMock()

        mock_google = MagicMock()
        mock_google.auth = mock_auth
        mock_google.auth.transport = MagicMock()
        mock_google.auth.transport.requests = mock_requests

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.auth": mock_auth,
            "google.auth.transport": mock_google.auth.transport,
            "google.auth.transport.requests": mock_requests
        }):
            token = get_vertex_access_token()
            self.assertEqual(token, "mock_cached_valid_token")
            # refresh should not be called when already valid
            self.assertFalse(mock_credentials.refresh.called)


if __name__ == "__main__":
    unittest.main()
