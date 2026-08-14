import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.prompts import build_system_instruction
from backend.app.agents.tools_declaration import GEMINI_TOOLS_DECLARATIONS


class TestPromptsAndDeclarations(unittest.TestCase):

    def test_build_system_instruction_with_full_profile(self):
        """Verify dynamic Indic persona injection from database profile."""
        profile = {
            "customer": {
                "customer_id": "CUST-101",
                "full_name": "Ramesh Sharma",
                "phone_number": "+919820198201",
                "preferred_language": "hinglish",
                "city": "Pune",
            },
            "vehicle": {
                "vin": "VIN-MAH-SCN-2024-001",
                "registration_number": "MH 12 RN 8921",
                "model_name": "Scorpio-N Z8L",
                "current_odometer_km": 20450,
                "service_due_type": "20,000 KM PMS",
            },
            "dealership": {
                "dealer_id": "DLR-PUN-01",
                "name": "Mahindra Sahyadri Auto Pune",
                "city": "Pune",
                "address": "Wakad Flyover, Pune",
                "service_advisor_phone": "+919822012345",
            }
        }

        prompt = build_system_instruction(profile)
        self.assertIn("Ramesh Sharma", prompt)
        self.assertIn("Scorpio-N Z8L", prompt)
        self.assertIn("20,450 km", prompt)
        self.assertIn("Mahindra Sahyadri Auto Pune", prompt)
        self.assertIn("DLR-PUN-01", prompt)
        self.assertIn("get_service_cost_estimate", prompt)
        self.assertIn("hold_service_slot", prompt)
        self.assertIn("180 seconds", prompt)

    def test_build_system_instruction_empty_fallback(self):
        """Verify safe fallbacks when profile data is empty."""
        prompt = build_system_instruction(None)
        self.assertIn("Valued Customer", prompt)
        self.assertIn("Pooja", prompt)

    def test_gemini_tools_declarations_schema(self):
        """Verify all 9 domain tools exist and adhere to Gemini function calling schema."""
        self.assertEqual(len(GEMINI_TOOLS_DECLARATIONS), 9)

        expected_tools = {
            "get_customer_vehicle_profile",
            "get_service_cost_estimate",
            "check_available_slots",
            "hold_service_slot",
            "book_service_appointment",
            "reschedule_reminder",
            "record_customer_disposition",
            "transfer_to_service_advisor",
            "end_call"
        }

        declared_names = {t["name"] for t in GEMINI_TOOLS_DECLARATIONS}
        self.assertEqual(expected_tools, declared_names)

        for tool in GEMINI_TOOLS_DECLARATIONS:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("parameters", tool)
            params = tool["parameters"]
            self.assertEqual(params["type"], "OBJECT")
            self.assertIn("properties", params)


if __name__ == "__main__":
    unittest.main()
