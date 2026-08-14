"""Unit tests for Application Config, GCP Secret Manager Integration, and Cloud Run Dynamic URLs."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import Settings, fetch_secret_from_gcp, settings
from backend.app.main import resolve_request_base_url, resolve_request_ws_url


class TestConfigAndSecrets(unittest.IsolatedAsyncioTestCase):

    def test_default_config_values(self):
        """Verify default project ID, Twilio phone number, and model settings."""
        settings = Settings()
        self.assertEqual(settings.GCP_PROJECT_ID, "1047195478355")
        self.assertEqual(settings.TWILIO_PHONE_NUMBER, "+13369154920")
        self.assertEqual(settings.GEMINI_MODEL, "gemini-live-2.5-flash-native-audio")
        self.assertIn("projects/1047195478355/secrets/TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID_SECRET)
        self.assertIn("projects/1047195478355/secrets/TWILIO_AUTH_TOKEN", settings.TWILIO_AUTH_TOKEN_SECRET)

    def test_fetch_secret_from_gcp_success(self):
        """Verify fetching secret from GCP Secret Manager with mocked client."""
        mock_payload = MagicMock()
        mock_payload.data = b"AC_mock_secret_sid_12345\n"
        mock_response = MagicMock()
        mock_response.payload = mock_payload

        mock_sm_client = MagicMock()
        mock_sm_client.access_secret_version.return_value = mock_response

        mock_sm_mod = MagicMock()
        mock_sm_mod.SecretManagerServiceClient = MagicMock(return_value=mock_sm_client)
        mock_google = MagicMock()
        mock_google.cloud = MagicMock()
        mock_google.cloud.secretmanager = mock_sm_mod

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google.cloud,
            "google.cloud.secretmanager": mock_sm_mod
        }):
            val = fetch_secret_from_gcp("projects/1047195478355/secrets/TWILIO_ACCOUNT_SID")
            self.assertEqual(val, "AC_mock_secret_sid_12345")
            mock_sm_client.access_secret_version.assert_called_once_with(
                name="projects/1047195478355/secrets/TWILIO_ACCOUNT_SID/versions/latest",
                timeout=1.0
            )

    def test_fetch_secret_from_gcp_short_name(self):
        """Verify fetching secret with simple name appends project path."""
        mock_payload = MagicMock()
        mock_payload.data = b"mock_token_abc\n"
        mock_response = MagicMock()
        mock_response.payload = mock_payload

        mock_sm_client = MagicMock()
        mock_sm_client.access_secret_version.return_value = mock_response

        mock_sm_mod = MagicMock()
        mock_sm_mod.SecretManagerServiceClient = MagicMock(return_value=mock_sm_client)
        mock_google = MagicMock()
        mock_google.cloud = MagicMock()
        mock_google.cloud.secretmanager = mock_sm_mod

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google.cloud,
            "google.cloud.secretmanager": mock_sm_mod
        }):
            val = fetch_secret_from_gcp("TWILIO_AUTH_TOKEN", project_id="1047195478355")
            self.assertEqual(val, "mock_token_abc")
            mock_sm_client.access_secret_version.assert_called_once_with(
                name="projects/1047195478355/secrets/TWILIO_AUTH_TOKEN/versions/latest",
                timeout=1.0
            )

    def test_fetch_secret_from_gcp_fallback(self):
        """Verify graceful fallback to None if Secret Manager client errors or is unavailable."""
        val = fetch_secret_from_gcp("NON_EXISTENT_SECRET")
        self.assertIsNone(val)

    def test_secret_auto_resolution_in_settings(self):
        """Verify Settings auto-resolves SID and Auth Token when secrets are available."""
        with patch.dict(os.environ, {"ENABLE_SECRET_MANAGER_LOOKUP": "1"}):
            with patch("backend.app.config.fetch_secret_from_gcp") as mock_fetch:
                def side_effect(secret_path, project_id):
                    if "TWILIO_ACCOUNT_SID" in secret_path:
                        return "AC_auto_fetched_sid"
                    if "TWILIO_AUTH_TOKEN" in secret_path:
                        return "auth_token_auto_fetched"
                    return None
                mock_fetch.side_effect = side_effect

                s = Settings(TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="")
                self.assertEqual(s.TWILIO_ACCOUNT_SID, "AC_auto_fetched_sid")
                self.assertEqual(s.TWILIO_AUTH_TOKEN, "auth_token_auto_fetched")
                self.assertTrue(s.is_twilio_configured)

    def test_cloud_run_dynamic_url_resolution(self):
        """Verify dynamic URL resolution from Cloud Run request headers."""
        # Simulated Cloud Run HTTPS Request
        mock_request = MagicMock()
        mock_request.headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host": "voice-reminder-xyz-uc.a.run.app",
            "host": "voice-reminder-xyz-uc.a.run.app"
        }
        mock_request.url.scheme = "https"
        mock_request.url.netloc = "voice-reminder-xyz-uc.a.run.app"

        base_url = resolve_request_base_url(mock_request)
        self.assertEqual(base_url, "https://voice-reminder-xyz-uc.a.run.app")

        ws_url = resolve_request_ws_url(mock_request)
        self.assertEqual(ws_url, "wss://voice-reminder-xyz-uc.a.run.app/ws/twilio/stream")

    def test_ws_base_url_variations(self):
        """Verify ws_base_url property handles http, https, and empty."""
        s1 = Settings(PUBLIC_BASE_URL="https://my-service.run.app")
        self.assertEqual(s1.ws_base_url, "wss://my-service.run.app")

        s2 = Settings(PUBLIC_BASE_URL="http://localhost:8000")
        self.assertEqual(s2.ws_base_url, "ws://localhost:8000")

        s3 = Settings(PUBLIC_BASE_URL="")
        self.assertEqual(s3.ws_base_url, "ws://localhost:8000")

    def test_cloud_run_k_service_fallback(self):
        """Verify fallback to K_SERVICE when request headers/host are absent."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.url.scheme = "https"
        mock_request.url.netloc = ""
        mock_request.base_url = None

        with patch.dict(os.environ, {"K_SERVICE": "voice-reminder-cr"}):
            base_url = resolve_request_base_url(mock_request)
            self.assertEqual(base_url, f"https://voice-reminder-cr-{settings.GCP_PROJECT_ID}.{settings.GCP_LOCATION}.run.app")

            ws_url = resolve_request_ws_url(mock_request)
            self.assertEqual(ws_url, f"wss://voice-reminder-cr-{settings.GCP_PROJECT_ID}.{settings.GCP_LOCATION}.run.app/ws/twilio/stream")

            s = Settings(PUBLIC_BASE_URL="", TWILIO_ACCOUNT_SID_SECRET="", TWILIO_AUTH_TOKEN_SECRET="")
            self.assertEqual(s.ws_base_url, f"wss://voice-reminder-cr-{settings.GCP_PROJECT_ID}.{settings.GCP_LOCATION}.run.app")

    def test_request_base_url_fallback(self):
        """Verify fallback to request.base_url when headers are absent."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.url.scheme = "https"
        mock_request.url.netloc = "custom-domain.example.com"
        mock_base_url = MagicMock()
        mock_base_url.netloc = "custom-domain.example.com"
        mock_base_url.__str__ = MagicMock(return_value="https://custom-domain.example.com")
        mock_request.base_url = mock_base_url

        with patch.dict(os.environ, {}, clear=True):
            base_url = resolve_request_base_url(mock_request)
            self.assertEqual(base_url, "https://custom-domain.example.com")

            ws_url = resolve_request_ws_url(mock_request)
            self.assertEqual(ws_url, "wss://custom-domain.example.com/ws/twilio/stream")

    async def test_twiml_stream_generation_async(self):
        """Verify get_twiml_stream produces valid XML containing dynamic wss stream URL."""
        from backend.app.main import get_twiml_stream

        mock_request = MagicMock()
        mock_request.headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host": "voice-reminder-cr-1047195478355.us-central1.run.app"
        }
        mock_request.method = "GET"
        mock_request.query_params = {"customer_id": "CUST-101", "vin": "VIN-MAH-001"}

        resp = await get_twiml_stream(mock_request, customer_id="CUST-101", vin="VIN-MAH-001")
        xml_content = resp.body.decode("utf-8")
        self.assertIn("wss://voice-reminder-cr-1047195478355.us-central1.run.app/ws/twilio/stream", xml_content)
        self.assertIn('value="CUST-101"', xml_content)
        self.assertIn('value="VIN-MAH-001"', xml_content)

    async def test_health_check_endpoint_async(self):
        """Verify health check endpoint returns Vertex AI and Twilio status."""
        from backend.app.main import health_check

        res = await health_check()
        self.assertEqual(res["status"], "HEALTHY")
        self.assertEqual(res["gcp_project_id"], "1047195478355")
        self.assertIn("vertex_configured", res)
        self.assertIn("twilio_configured", res)


if __name__ == "__main__":
    unittest.main()
