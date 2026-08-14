import json
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestDatabaseSeed(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Execute schema DDL
        schema_path = os.path.join(os.path.dirname(__file__), "..", "backend", "schema.sql")
        with open(schema_path, "r") as f:
            ddl = f.read()
        self.cursor.executescript(ddl)

    def tearDown(self):
        self.conn.close()

    def test_dealerships_seeding_and_constraints(self):
        """Verify dealership table schema and insertion."""
        dealers = [
            ("DLR-PUN-01", "Mahindra Sahyadri Auto Pune", "Pune", "Maharashtra", "Wakad Flyover, Pune", "+912067891234", "https://maps.google.com/?q=Pune", "+919822012345", 6),
            ("DLR-BLR-01", "Mahindra Sireesh Auto Bengaluru", "Bengaluru", "Karnataka", "Outer Ring Rd, Bengaluru", "+918045678901", "https://maps.google.com/?q=Bangalore", "+919845012345", 8),
            ("DLR-CHD-01", "Swaraj Agro Tractors Chandigarh", "Chandigarh", "Punjab", "GT Road, Mohali", "+911722894567", "https://maps.google.com/?q=Mohali", "+919814012345", 4),
        ]
        self.cursor.executemany("""
            INSERT INTO dealerships (dealer_id, name, city, state, address, phone_number, maps_url, service_advisor_phone, total_service_bays)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, dealers)
        self.conn.commit()

        self.cursor.execute("SELECT COUNT(*) as count FROM dealerships")
        self.assertEqual(self.cursor.fetchone()["count"], 3)

    def test_customer_vehicle_relationships(self):
        """Verify customer to vehicle foreign keys and joined queries."""
        # 1. Dealer
        self.cursor.execute("""
            INSERT INTO dealerships (dealer_id, name, city, state, address, phone_number)
            VALUES ('DLR-PUN-01', 'Sahyadri Auto', 'Pune', 'MH', 'Pune', '+912011112222')
        """)

        # 2. Customers
        customers = [
            ("CUST-101", "Ramesh Sharma", "+919820198201", "ramesh@example.in", "hinglish", "Pune", 1),
            ("CUST-102", "Priya Patel", "+919876543210", "priya@example.in", "en", "Bengaluru", 1),
            ("CUST-103", "Vikram Singh", "+919811223344", "vikram@example.in", "hi", "Pune", 1),
            ("CUST-104", "Gurpreet Singh", "+919814556677", "gurpreet@example.in", "hinglish", "Chandigarh", 1),
            ("CUST-105", "Anita Deshmukh", "+919890112233", "anita@example.in", "mr", "Pune", 1),
        ]
        self.cursor.executemany("""
            INSERT INTO customers (customer_id, full_name, phone_number, email, preferred_language, city, consent_dnd_scrubbed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, customers)

        # 3. Vehicles
        vehicles = [
            ("VIN-MAH-SCN-2024-001", "CUST-101", "MH 12 RN 8921", "Scorpio-N Z8L", "Diesel", "2024-02-15", 20450, "2025-08-10", 10200, 6, 10000, "20,000 KM PMS", "DLR-PUN-01"),
            ("VIN-MAH-XUV-2023-088", "CUST-102", "MH 14 TC 4512", "XUV700 AX7", "Petrol", "2023-05-20", 30800, "2025-06-15", 20100, 6, 10000, "30,000 KM PMS", "DLR-PUN-01"),
            ("VIN-MAH-THR-2024-512", "CUST-103", "DL 3C AB 9012", "Thar LX", "Diesel", "2024-03-10", 10120, "2024-04-12", 1050, 6, 10000, "10,000 KM PMS", "DLR-PUN-01"),
            ("VIN-SWR-855-2022-771", "CUST-104", "PB 11 AG 3321", "Swaraj 855 FE", "Diesel", "2022-10-05", 480, "2023-11-20", 250, 12, 250, "500 HRS Tractor PMS", "DLR-PUN-01"),
            ("VIN-MAH-SCL-2023-119", "CUST-105", "MH 02 ER 6654", "Scorpio Classic S11", "Diesel", "2023-01-18", 40200, "2025-07-02", 30000, 6, 10000, "40,000 KM PMS", "DLR-PUN-01"),
        ]
        self.cursor.executemany("""
            INSERT INTO vehicles (vin, customer_id, registration_number, model_name, fuel_type, purchase_date, current_odometer_km, last_service_date, last_service_mileage_km, service_interval_months, service_interval_km, service_due_type, assigned_dealer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, vehicles)
        self.conn.commit()

        # Joined profile query
        self.cursor.execute("""
            SELECT c.full_name, c.preferred_language, v.model_name, v.registration_number, d.name as dealer_name
            FROM customers c
            JOIN vehicles v ON c.customer_id = v.customer_id
            JOIN dealerships d ON v.assigned_dealer_id = d.dealer_id
            WHERE c.customer_id = 'CUST-101'
        """)
        row = self.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["full_name"], "Ramesh Sharma")
        self.assertEqual(row["model_name"], "Scorpio-N Z8L")
        self.assertEqual(row["preferred_language"], "hinglish")

    def test_pricing_catalog_seeding(self):
        """Verify pricing catalog itemized costs and checklist serialization."""
        checklist = json.dumps([
            "Engine Oil Replacement (Mahindra Maximile)",
            "Oil Filter Replacement",
            "Brake Pad Inspection",
            "Wheel Alignment & Balancing"
        ])
        self.cursor.execute("""
            INSERT INTO service_cost_catalog (model_name, service_type, mileage_interval_km, estimated_parts_cost, estimated_labor_cost, engine_oil_cost, tax_percentage, total_estimated_cost, included_checklist)
            VALUES ('Scorpio-N Z8L', 'PERIODIC_MAINTENANCE', 20000, 2400.0, 1200.0, 1600.0, 18.0, 6136.0, ?)
        """, (checklist,))
        self.conn.commit()

        self.cursor.execute("SELECT * FROM service_cost_catalog WHERE model_name = 'Scorpio-N Z8L'")
        item = self.cursor.fetchone()
        self.assertIsNotNone(item)
        self.assertEqual(item["total_estimated_cost"], 6136.0)
        items_list = json.loads(item["included_checklist"])
        self.assertIn("Engine Oil Replacement (Mahindra Maximile)", items_list)


if __name__ == "__main__":
    unittest.main()
