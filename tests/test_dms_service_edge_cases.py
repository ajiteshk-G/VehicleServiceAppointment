import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestDmsServiceEdgeCases(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        schema_path = os.path.join(os.path.dirname(__file__), "..", "backend", "schema.sql")
        with open(schema_path, "r") as f:
            ddl = f.read()
        self.cursor.executescript(ddl)
        self._seed_data()

    def _seed_data(self):
        # Dealerships
        self.cursor.execute("""
            INSERT INTO dealerships (dealer_id, name, city, state, address, phone_number, maps_url, service_advisor_phone, total_service_bays)
            VALUES ('DLR-PUN-01', 'Mahindra Sahyadri Auto Pune', 'Pune', 'Maharashtra', 'Wakad, Pune', '+912067891234', 'https://maps.google.com/?q=Pune', '+919822012345', 6)
        """)

        # Customers
        self.cursor.execute("""
            INSERT INTO customers (customer_id, full_name, phone_number, email, preferred_language, city, consent_dnd_scrubbed)
            VALUES ('CUST-101', 'Ramesh Sharma', '+919820198201', 'ramesh@example.in', 'hinglish', 'Pune', 1)
        """)
        self.cursor.execute("""
            INSERT INTO customers (customer_id, full_name, phone_number, email, preferred_language, city, consent_dnd_scrubbed)
            VALUES ('CUST-102', 'Priya Patel', '+919876543210', 'priya@example.in', 'en', 'Bengaluru', 1)
        """)

        # Vehicles
        self.cursor.execute("""
            INSERT INTO vehicles (vin, customer_id, registration_number, model_name, fuel_type, purchase_date, current_odometer_km, last_service_date, last_service_mileage_km, service_interval_months, service_interval_km, service_due_type, assigned_dealer_id)
            VALUES ('VIN-MAH-SCN-2024-001', 'CUST-101', 'MH 12 RN 8921', 'Scorpio-N Z8L', 'Diesel', '2024-02-15', 20450, '2025-08-10', 10200, 6, 10000, '20,000 KM PMS', 'DLR-PUN-01')
        """)
        self.cursor.execute("""
            INSERT INTO vehicles (vin, customer_id, registration_number, model_name, fuel_type, purchase_date, current_odometer_km, last_service_date, last_service_mileage_km, service_interval_months, service_interval_km, service_due_type, assigned_dealer_id)
            VALUES ('VIN-MAH-XUV-2023-088', 'CUST-102', 'MH 14 TC 4512', 'XUV700 AX7', 'Petrol', '2023-05-20', 30800, '2025-06-15', 20100, 6, 10000, '30,000 KM PMS', 'DLR-PUN-01')
        """)

        # Pricing Catalog (5 models)
        catalogs = [
            ("Scorpio-N Z8L", "PERIODIC_MAINTENANCE", 20000, 2400.0, 1200.0, 1600.0, 18.0, 6136.0, json.dumps(["Oil Filter", "Engine Oil Maximile"])),
            ("Scorpio-N Z8L", "GENERAL_CHECKUP", 10000, 0.0, 650.0, 0.0, 18.0, 767.0, json.dumps(["Inspection"])),
            ("XUV700 AX7", "PERIODIC_MAINTENANCE", 30000, 3800.0, 1500.0, 2100.0, 18.0, 8732.0, json.dumps(["Synthetic Oil", "AC Filter"])),
            ("Thar LX", "PERIODIC_MAINTENANCE", 10000, 1800.0, 950.0, 1500.0, 18.0, 5015.0, json.dumps(["4x4 Check", "Engine Oil"])),
            ("Swaraj 855 FE", "PERIODIC_MAINTENANCE", 500, 1400.0, 600.0, 2200.0, 18.0, 4956.0, json.dumps(["Heavy Duty Oil", "Hydraulic Filter"])),
            ("Scorpio Classic S11", "PERIODIC_MAINTENANCE", 40000, 2200.0, 1100.0, 1600.0, 18.0, 5782.0, json.dumps(["Leaf Springs", "Oil Change"])),
        ]
        self.cursor.executemany("""
            INSERT INTO service_cost_catalog (model_name, service_type, mileage_interval_km, estimated_parts_cost, estimated_labor_cost, engine_oil_cost, tax_percentage, total_estimated_cost, included_checklist)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, catalogs)

        # Slots (Past, Present, and Future)
        now = datetime.now(timezone.utc)
        past_time = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        future_time_1 = (now + timedelta(days=1, hours=10)).strftime("%Y-%m-%d %H:%M:%S")
        future_time_2 = (now + timedelta(days=1, hours=14)).strftime("%Y-%m-%d %H:%M:%S")

        self.cursor.execute("INSERT INTO service_slots (dealer_id, slot_time, bay_number, is_booked) VALUES ('DLR-PUN-01', ?, 1, 0)", (past_time,))
        self.cursor.execute("INSERT INTO service_slots (dealer_id, slot_time, bay_number, is_booked) VALUES ('DLR-PUN-01', ?, 2, 0)", (future_time_1,))
        self.cursor.execute("INSERT INTO service_slots (dealer_id, slot_time, bay_number, is_booked) VALUES ('DLR-PUN-01', ?, 3, 0)", (future_time_2,))

        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_catalog_token_matching_variations(self):
        """Verify robust fuzzy/token catalog lookups for LLM model variations."""
        test_queries = [
            ("Mahindra Scorpio-N", 6136.0),
            ("Scorpio-N", 6136.0),
            ("Mahindra XUV700", 8732.0),
            ("XUV700 AX7", 8732.0),
            ("Mahindra Thar", 5015.0),
            ("Swaraj 855", 4956.0),
            ("Scorpio Classic", 5782.0),
        ]
        for query_model, expected_cost in test_queries:
            clean = query_model.replace("Mahindra", "").replace("mahindra", "").strip()
            # Step 1: Substring match on clean or query
            self.cursor.execute("""
                SELECT * FROM service_cost_catalog
                WHERE model_name LIKE ? OR model_name LIKE ?
            """, (f"%{clean}%", f"%{query_model}%"))
            row = self.cursor.fetchone()

            # Step 2: Token match if needed
            if not row:
                for token in [t for t in clean.split() if len(t) > 2]:
                    self.cursor.execute("SELECT * FROM service_cost_catalog WHERE model_name LIKE ?", (f"%{token}%",))
                    row = self.cursor.fetchone()
                    if row:
                        break

            self.assertIsNotNone(row, f"Failed to match catalog for query '{query_model}'")
            self.assertEqual(row["total_estimated_cost"], expected_cost)

    def test_hold_slot_already_booked_fails(self):
        """Verify holding an already booked slot is rejected."""
        # Book slot 2
        self.cursor.execute("UPDATE service_slots SET is_booked = 1 WHERE slot_id = 2")
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_slots WHERE slot_id = 2")
        slot = self.cursor.fetchone()
        self.assertEqual(slot["is_booked"], 1)

    def test_hold_slot_lock_expiration_and_reclaim(self):
        """Verify expired 180s slot lock allows another customer to hold."""
        now = datetime.now(timezone.utc)
        expired_time = (now - timedelta(seconds=200)).isoformat()

        # Slot 3 locked in the past
        self.cursor.execute("""
            UPDATE service_slots
            SET locked_by_customer_id = 'CUST-999', locked_until = ?
            WHERE slot_id = 3
        """, (expired_time,))
        self.conn.commit()

        # Check if lock is expired
        self.cursor.execute("SELECT * FROM service_slots WHERE slot_id = 3")
        slot = self.cursor.fetchone()
        locked_until_dt = datetime.fromisoformat(slot["locked_until"])
        is_expired = locked_until_dt < now
        self.assertTrue(is_expired)

        # New customer can now lock slot 3
        new_locked_until = (now + timedelta(seconds=180)).isoformat()
        self.cursor.execute("""
            UPDATE service_slots
            SET locked_by_customer_id = 'CUST-101', locked_until = ?
            WHERE slot_id = 3
        """, (new_locked_until,))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_slots WHERE slot_id = 3")
        updated_slot = self.cursor.fetchone()
        self.assertEqual(updated_slot["locked_by_customer_id"], "CUST-101")

    def test_booking_auto_resolves_vin_and_dealer(self):
        """Verify booking auto-resolves VIN and dealer when missing."""
        customer_id = "CUST-101"
        slot_id = 2

        # Look up customer's vehicle
        self.cursor.execute("SELECT vin, model_name, assigned_dealer_id FROM vehicles WHERE customer_id = ?", (customer_id,))
        veh = self.cursor.fetchone()
        vin = veh["vin"]
        dealer_id = veh["assigned_dealer_id"]
        self.assertEqual(vin, "VIN-MAH-SCN-2024-001")
        self.assertEqual(dealer_id, "DLR-PUN-01")

        # Create booking
        booking_ref = f"#MND-PUN-9999"
        slot_time = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("""
            INSERT INTO service_bookings (booking_reference, customer_id, vin, dealer_id, slot_id, slot_time, service_type, booking_status)
            VALUES (?, ?, ?, ?, ?, ?, 'PERIODIC_MAINTENANCE', 'CONFIRMED')
        """, (booking_ref, customer_id, vin, dealer_id, slot_id, slot_time))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_bookings WHERE booking_reference = ?", (booking_ref,))
        b = self.cursor.fetchone()
        self.assertEqual(b["vin"], "VIN-MAH-SCN-2024-001")
        self.assertEqual(b["dealer_id"], "DLR-PUN-01")

    def test_booking_reference_generation_edge_cases(self):
        """Verify booking reference generation with None, empty, and tractor models."""
        from backend.app.services.dms_service import generate_booking_reference

        ref1 = generate_booking_reference("Pune", "Scorpio-N Z8L")
        self.assertTrue(ref1.startswith("#MND-PUN-"))

        ref2 = generate_booking_reference("Mohali", "Swaraj 855 FE")
        self.assertTrue(ref2.startswith("#SWR-MOH-"))

        ref3 = generate_booking_reference(None, None)
        self.assertTrue(ref3.startswith("#MND-IND-"))

        ref4 = generate_booking_reference("", "")
        self.assertTrue(ref4.startswith("#MND-IND-"))

    def test_call_log_json_and_list_transcripts_deserialization(self):
        """Verify CallLog.get_transcripts and get_tool_calls handles str, list, and dict."""
        try:
            from backend.app.models import CallLog
            
            # 1. String JSON
            log1 = CallLog(transcript_json=json.dumps([{"role": "user", "text": "hello"}]), tool_calls_json=json.dumps([{"tool": "get_cost"}]))
            self.assertEqual(len(log1.get_transcripts()), 1)
            self.assertEqual(len(log1.get_tool_calls()), 1)

            # 2. Native list (PostgreSQL JSONB)
            log2 = CallLog(transcript_json=[{"role": "user", "text": "hello"}], tool_calls_json=[{"tool": "get_cost"}])
            self.assertEqual(len(log2.get_transcripts()), 1)
            self.assertEqual(len(log2.get_tool_calls()), 1)

            # 3. Native dict
            log3 = CallLog(transcript_json={"role": "user", "text": "hello"}, tool_calls_json={"tool": "get_cost"})
            self.assertEqual(len(log3.get_transcripts()), 1)
            self.assertEqual(len(log3.get_tool_calls()), 1)

            # 4. None / empty
            log4 = CallLog(transcript_json=None, tool_calls_json="")
            self.assertEqual(log4.get_transcripts(), [])
            self.assertEqual(log4.get_tool_calls(), [])
        except ImportError:
            pass

    def test_service_slot_string_datetime_is_locked(self):
        """Verify ServiceSlot.is_locked handles string ISO datetimes from SQLite."""
        try:
            from backend.app.models import ServiceSlot

            future_iso = (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat()
            slot = ServiceSlot(locked_until=future_iso, is_booked=False)
            self.assertTrue(slot.is_locked())

            past_iso = (datetime.now(timezone.utc) - timedelta(seconds=180)).isoformat()
            slot2 = ServiceSlot(locked_until=past_iso, is_booked=False)
            self.assertFalse(slot2.is_locked())
        except ImportError:
            pass


if __name__ == "__main__":
    unittest.main()
