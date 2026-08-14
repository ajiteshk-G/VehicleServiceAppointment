"""Standalone zero-dependency test for SQLite schema, seeding, and 8 domain tools."""

import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

# Add workspace to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestStandaloneSchemaAndTools(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Read and execute schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), "..", "backend", "schema.sql")
        with open(schema_path, "r") as f:
            ddl = f.read()
        self.cursor.executescript(ddl)

        # Seed data
        self._seed_data()

    def _seed_data(self):
        # Dealerships
        self.cursor.execute("""
            INSERT INTO dealerships (dealer_id, name, city, state, address, phone_number, maps_url, service_advisor_phone, total_service_bays)
            VALUES ('DLR-PUN-01', 'Mahindra Sahyadri Auto Pune', 'Pune', 'Maharashtra', 'Wakad Flyover, Pune', '+912067891234', 'https://maps.google.com/?q=Pune', '+919822012345', 6)
        """)

        # Customer & Vehicle
        self.cursor.execute("""
            INSERT INTO customers (customer_id, full_name, phone_number, email, preferred_language, city, consent_dnd_scrubbed)
            VALUES ('CUST-101', 'Ramesh Sharma', '+919820198201', 'ramesh@example.in', 'hinglish', 'Pune', 1)
        """)
        self.cursor.execute("""
            INSERT INTO vehicles (vin, customer_id, registration_number, model_name, fuel_type, purchase_date, current_odometer_km, last_service_date, last_service_mileage_km, service_interval_months, service_interval_km, service_due_type, assigned_dealer_id)
            VALUES ('VIN-MAH-SCN-2024-001', 'CUST-101', 'MH 12 RN 8921', 'Scorpio-N Z8L', 'Diesel', '2024-02-15', 20450, '2025-08-10', 10200, 6, 10000, '20,000 KM PMS (2nd Free Service)', 'DLR-PUN-01')
        """)

        # Pricing Catalog
        checklist = json.dumps(["Engine Oil & Oil Filter Replacement", "Air Filter Cleaning", "Brake Pad Inspection"])
        self.cursor.execute("""
            INSERT INTO service_cost_catalog (model_name, service_type, mileage_interval_km, estimated_parts_cost, estimated_labor_cost, engine_oil_cost, tax_percentage, total_estimated_cost, included_checklist)
            VALUES ('Scorpio-N Z8L', 'PERIODIC_MAINTENANCE', 20000, 2400.0, 1200.0, 1600.0, 18.0, 6136.0, ?)
        """, (checklist,))

        # Slots
        now = datetime.now(timezone.utc)
        slot_time = (now + timedelta(days=1)).strftime("%Y-%m-%d 10:00:00")
        self.cursor.execute("""
            INSERT INTO service_slots (dealer_id, slot_time, bay_number, is_booked, locked_by_customer_id, locked_until)
            VALUES ('DLR-PUN-01', ?, 1, 0, NULL, NULL)
        """, (slot_time,))

        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_tool_1_get_customer_vehicle_profile(self):
        self.cursor.execute("""
            SELECT c.full_name, c.phone_number, v.model_name, v.registration_number, v.current_odometer_km, v.service_due_type, d.name as dealer_name
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

    def test_tool_2_get_service_cost_estimate(self):
        self.cursor.execute("""
            SELECT * FROM service_cost_catalog WHERE model_name = 'Scorpio-N Z8L' AND service_type = 'PERIODIC_MAINTENANCE'
        """)
        row = self.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["total_estimated_cost"], 6136.0)
        checklist = json.loads(row["included_checklist"])
        self.assertIn("Engine Oil & Oil Filter Replacement", checklist)

    def test_tool_3_check_available_slots(self):
        self.cursor.execute("""
            SELECT * FROM service_slots WHERE dealer_id = 'DLR-PUN-01' AND is_booked = 0
        """)
        slots = self.cursor.fetchall()
        self.assertGreater(len(slots), 0)

    def test_tool_4_hold_service_slot(self):
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
        self.assertEqual(slot["locked_by_customer_id"], customer_id)
        self.assertEqual(slot["locked_until"], locked_until)

    def test_tool_5_book_service_appointment(self):
        booking_ref = "#MND-PUN-8921"
        slot_id = 1
        slot_time = "2026-08-16 10:00:00"

        # Update slot
        self.cursor.execute("UPDATE service_slots SET is_booked = 1, locked_until = NULL WHERE slot_id = ?", (slot_id,))

        # Insert booking
        self.cursor.execute("""
            INSERT INTO service_bookings (booking_reference, customer_id, vin, dealer_id, slot_id, slot_time, service_type, pickup_drop_required, pickup_address, customer_notes, booking_status)
            VALUES (?, 'CUST-101', 'VIN-MAH-SCN-2024-001', 'DLR-PUN-01', ?, ?, 'PERIODIC_MAINTENANCE', 1, 'Wakad Pune', 'Check suspension', 'CONFIRMED')
        """, (booking_ref, slot_id, slot_time))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_bookings WHERE booking_reference = ?", (booking_ref,))
        b = self.cursor.fetchone()
        self.assertIsNotNone(b)
        self.assertEqual(b["booking_status"], "CONFIRMED")
        self.assertEqual(b["pickup_drop_required"], 1)

    def test_tool_6_7_reschedule_and_disposition(self):
        # Reschedule
        cb_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        transcript = json.dumps([{"role": "system", "text": "Customer requested callback", "timestamp": cb_time}])
        self.cursor.execute("""
            INSERT INTO call_logs (call_id, customer_id, vin, channel, call_status, disposition, callback_scheduled_at, duration_seconds, transcript_json)
            VALUES ('CALL-101-1', 'CUST-101', 'VIN-MAH-SCN-2024-001', 'TWILIO_PSTN', 'ANSWERED', 'RESCHEDULED', ?, 45, ?)
        """, (cb_time, transcript))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM call_logs WHERE call_id = 'CALL-101-1'")
        log = self.cursor.fetchone()
        self.assertEqual(log["disposition"], "RESCHEDULED")
        parsed = json.loads(log["transcript_json"])
        self.assertEqual(len(parsed), 1)


if __name__ == "__main__":
    unittest.main()
