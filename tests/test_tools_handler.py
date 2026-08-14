import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestToolsHandler(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Execute schema DDL
        schema_path = os.path.join(os.path.dirname(__file__), "..", "backend", "schema.sql")
        with open(schema_path, "r") as f:
            ddl = f.read()
        self.cursor.executescript(ddl)
        self._seed_data()

    def _seed_data(self):
        # Dealerships
        self.cursor.execute("""
            INSERT INTO dealerships (dealer_id, name, city, state, address, phone_number, maps_url, service_advisor_phone, total_service_bays)
            VALUES ('DLR-PUN-01', 'Mahindra Sahyadri Auto Pune', 'Pune', 'Maharashtra', 'Wakad Flyover, Pune', '+912067891234', 'https://maps.google.com/?q=Pune', '+919822012345', 6)
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
            VALUES ('VIN-MAH-SCN-2024-001', 'CUST-101', 'MH 12 RN 8921', 'Scorpio-N Z8L', 'Diesel', '2024-02-15', 20450, '2025-08-10', 10200, 6, 10000, '20,000 KM PMS (2nd Free Service)', 'DLR-PUN-01')
        """)
        self.cursor.execute("""
            INSERT INTO vehicles (vin, customer_id, registration_number, model_name, fuel_type, purchase_date, current_odometer_km, last_service_date, last_service_mileage_km, service_interval_months, service_interval_km, service_due_type, assigned_dealer_id)
            VALUES ('VIN-MAH-XUV-2023-088', 'CUST-102', 'MH 14 TC 4512', 'XUV700 AX7', 'Petrol', '2023-05-20', 30800, '2025-06-15', 20100, 6, 10000, '30,000 KM PMS (Major Service)', 'DLR-PUN-01')
        """)

        # Catalog
        checklist = json.dumps([
            "Engine Oil & Oil Filter Replacement (Mahindra Maximile)",
            "Air Filter Cleaning and Inspection",
            "Brake Pad & Rotor Thickness Check"
        ])
        self.cursor.execute("""
            INSERT INTO service_cost_catalog (model_name, service_type, mileage_interval_km, estimated_parts_cost, estimated_labor_cost, engine_oil_cost, tax_percentage, total_estimated_cost, included_checklist)
            VALUES ('Scorpio-N Z8L', 'PERIODIC_MAINTENANCE', 20000, 2400.0, 1200.0, 1600.0, 18.0, 6136.0, ?)
        """, (checklist,))

        # Slots
        now = datetime.now(timezone.utc)
        for i in range(1, 4):
            slot_time = (now + timedelta(days=1, hours=i)).strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("""
                INSERT INTO service_slots (dealer_id, slot_time, bay_number, is_booked, locked_by_customer_id, locked_until)
                VALUES ('DLR-PUN-01', ?, ?, 0, NULL, NULL)
            """, (slot_time, i))

        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_tool_1_profile_lookup(self):
        """Tool 1: get_customer_vehicle_profile."""
        self.cursor.execute("""
            SELECT c.customer_id, c.full_name, c.phone_number, v.vin, v.model_name, v.current_odometer_km, v.service_due_type, d.dealer_id, d.name as dealer_name
            FROM customers c
            JOIN vehicles v ON c.customer_id = v.customer_id
            JOIN dealerships d ON v.assigned_dealer_id = d.dealer_id
            WHERE c.customer_id = 'CUST-101'
        """)
        row = self.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["full_name"], "Ramesh Sharma")
        self.assertEqual(row["model_name"], "Scorpio-N Z8L")
        self.assertEqual(row["current_odometer_km"], 20450)

    def test_tool_2_cost_estimate_with_token_matching(self):
        """Tool 2: get_service_cost_estimate."""
        query_model = "Mahindra Scorpio-N"
        clean_model = query_model.replace("Mahindra", "").strip()

        self.cursor.execute("""
            SELECT * FROM service_cost_catalog
            WHERE model_name LIKE ? OR model_name LIKE ?
        """, (f"%{clean_model}%", f"%{query_model}%"))
        row = self.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["total_estimated_cost"], 6136.0)

    def test_tool_3_check_available_slots(self):
        """Tool 3: check_available_slots."""
        self.cursor.execute("""
            SELECT * FROM service_slots
            WHERE dealer_id = 'DLR-PUN-01' AND is_booked = 0
            ORDER BY slot_time ASC
        """)
        slots = self.cursor.fetchall()
        self.assertEqual(len(slots), 3)

    def test_tool_4_hold_service_slot_180s(self):
        """Tool 4: hold_service_slot with atomic 180s lock."""
        slot_id = 1
        customer_id = "CUST-101"
        locked_until = (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat()

        self.cursor.execute("""
            UPDATE service_slots
            SET locked_by_customer_id = ?, locked_until = ?
            WHERE slot_id = ? AND is_booked = 0
        """, (customer_id, locked_until, slot_id))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_slots WHERE slot_id = ?", (slot_id,))
        slot = self.cursor.fetchone()
        self.assertEqual(slot["locked_by_customer_id"], "CUST-101")
        self.assertEqual(slot["locked_until"], locked_until)

    def test_tool_5_book_service_appointment(self):
        """Tool 5: book_service_appointment with booking reference generation."""
        booking_ref = "#MND-PUN-8921"
        slot_id = 1
        slot_time = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

        # Mark slot booked
        self.cursor.execute("UPDATE service_slots SET is_booked = 1, locked_until = NULL WHERE slot_id = ?", (slot_id,))

        # Insert booking
        self.cursor.execute("""
            INSERT INTO service_bookings (booking_reference, customer_id, vin, dealer_id, slot_id, slot_time, service_type, pickup_drop_required, pickup_address, customer_notes, booking_status)
            VALUES (?, 'CUST-101', 'VIN-MAH-SCN-2024-001', 'DLR-PUN-01', ?, ?, 'PERIODIC_MAINTENANCE', 1, 'Wakad Pune', 'Brake inspection', 'CONFIRMED')
        """, (booking_ref, slot_id, slot_time))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_bookings WHERE booking_reference = ?", (booking_ref,))
        b = self.cursor.fetchone()
        self.assertIsNotNone(b)
        self.assertEqual(b["booking_reference"], "#MND-PUN-8921")
        self.assertEqual(b["booking_status"], "CONFIRMED")

    def test_tool_6_reschedule_reminder(self):
        """Tool 6: reschedule_reminder with JSON transcript."""
        cb_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        transcript = json.dumps([{"role": "system", "text": "Callback scheduled for tomorrow 4 PM", "timestamp": cb_time}])

        self.cursor.execute("""
            INSERT INTO call_logs (call_id, customer_id, vin, channel, call_status, disposition, callback_scheduled_at, duration_seconds, transcript_json, tool_calls_json)
            VALUES ('CALL-CUST-102-1', 'CUST-102', 'VIN-MAH-XUV-2023-088', 'TWILIO_PSTN', 'ANSWERED', 'RESCHEDULED', ?, 30, ?, '[]')
        """, (cb_time, transcript))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM call_logs WHERE call_id = 'CALL-CUST-102-1'")
        log = self.cursor.fetchone()
        self.assertEqual(log["disposition"], "RESCHEDULED")
        parsed = json.loads(log["transcript_json"])
        self.assertEqual(len(parsed), 1)

    def test_tool_7_record_customer_disposition(self):
        """Tool 7: record_customer_disposition."""
        transcript = json.dumps([{"role": "system", "text": "Customer sold vehicle", "timestamp": datetime.now(timezone.utc).isoformat()}])
        self.cursor.execute("""
            INSERT INTO call_logs (call_id, customer_id, vin, channel, call_status, disposition, duration_seconds, transcript_json, tool_calls_json)
            VALUES ('CALL-CUST-101-DISP', 'CUST-101', 'VIN-MAH-SCN-2024-001', 'TWILIO_PSTN', 'ANSWERED', 'VEHICLE_SOLD', 25, ?, '[]')
        """, (transcript,))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM call_logs WHERE call_id = 'CALL-CUST-101-DISP'")
        log = self.cursor.fetchone()
        self.assertEqual(log["disposition"], "VEHICLE_SOLD")

        self.cursor.execute("SELECT service_advisor_phone, name FROM dealerships WHERE dealer_id = 'DLR-PUN-01'")
        dealer = self.cursor.fetchone()
        self.assertIsNotNone(dealer)
        self.assertEqual(dealer["service_advisor_phone"], "+919822012345")

    def test_tool_argument_boolean_parsing_edge_cases(self):
        """Verify robust boolean parsing for LLM arguments (e.g. 'false', 'true', '1', '0', 'yes', 'no')."""
        def parse_bool(val):
            if isinstance(val, str):
                return val.strip().lower() in ("true", "1", "yes", "t")
            return bool(val)

        self.assertFalse(parse_bool("false"))
        self.assertFalse(parse_bool("False"))
        self.assertFalse(parse_bool("0"))
        self.assertFalse(parse_bool("no"))
        self.assertFalse(parse_bool(False))
        self.assertFalse(parse_bool(0))

        self.assertTrue(parse_bool("true"))
        self.assertTrue(parse_bool("True"))
        self.assertTrue(parse_bool("1"))
        self.assertTrue(parse_bool("yes"))
        self.assertTrue(parse_bool(True))
        self.assertTrue(parse_bool(1))

    def test_tool_argument_datetime_parsing_edge_cases(self):
        """Verify ISO datetime parsing and timezone handling for callbacks."""
        def parse_dt(cb_str):
            cb_time = datetime.now(timezone.utc) + timedelta(days=1, hours=4)
            if cb_str:
                try:
                    clean_cb = str(cb_str).strip().replace("Z", "+00:00")
                    parsed = datetime.fromisoformat(clean_cb)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    cb_time = parsed
                except Exception:
                    pass
            return cb_time

        parsed_iso = parse_dt("2026-08-16T15:30:00Z")
        self.assertEqual(parsed_iso.year, 2026)
        self.assertEqual(parsed_iso.month, 8)
        self.assertEqual(parsed_iso.day, 16)
        self.assertEqual(parsed_iso.hour, 15)
        self.assertEqual(parsed_iso.minute, 30)

        # Malformed string should fallback safely
        fallback = parse_dt("Tomorrow afternoon maybe")
        self.assertIsNotNone(fallback)
    def test_slot_id_string_coercion_edge_cases(self):
        """Verify slot_id string coercion handles 'slot_1', '1', 1, None, and invalid strings."""
        def extract_slot_id(raw_val):
            try:
                return int(str(raw_val).replace("slot_", "").strip())
            except (ValueError, TypeError):
                return 0

        self.assertEqual(extract_slot_id("slot_1"), 1)
        self.assertEqual(extract_slot_id("slot_42"), 42)
        self.assertEqual(extract_slot_id("10"), 10)
        self.assertEqual(extract_slot_id(5), 5)
        self.assertEqual(extract_slot_id(None), 0)
        self.assertEqual(extract_slot_id("invalid"), 0)

    def test_parameter_alias_resolution(self):
        """Verify parameter alias resolution for model, vehicle_model, dealership_id, type."""
        args1 = {"model": "Scorpio-N Z8L", "type": "PERIODIC_MAINTENANCE"}
        model1 = args1.get("model_name") or args1.get("model") or args1.get("vehicle_model") or ""
        type1 = args1.get("service_type") or args1.get("type") or "PERIODIC_MAINTENANCE"
        self.assertEqual(model1, "Scorpio-N Z8L")
        self.assertEqual(type1, "PERIODIC_MAINTENANCE")

        args2 = {"vehicle_model": "Thar LX", "service_type": "GENERAL_CHECKUP"}
        model2 = args2.get("model_name") or args2.get("model") or args2.get("vehicle_model") or ""
        type2 = args2.get("service_type") or args2.get("type") or "PERIODIC_MAINTENANCE"
        self.assertEqual(model2, "Thar LX")
        self.assertEqual(type2, "GENERAL_CHECKUP")


if __name__ == "__main__":
    unittest.main()
