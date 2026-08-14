"""Comprehensive Async Integration Tests for DMS Service and Gemini Tools Execution."""

import asyncio
import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from backend.app.database import Base
    from backend.app.models import Dealership, Customer, Vehicle, ServiceCostCatalog, ServiceSlot, ServiceBooking, CallLog
    from backend.app.services import dms_service, campaign_service
    from backend.app.agents.tools_handler import execute_tool_call
    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False


@unittest.skipUnless(_SQLALCHEMY_AVAILABLE, "SQLAlchemy not installed in test environment")
class TestAsyncToolsAndDms(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create an in-memory SQLite async engine
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            future=True,
            connect_args={"check_same_thread": False}
        )
        self.SessionLocal = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await self._seed_data()

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def _seed_data(self):
        async with self.SessionLocal() as session:
            # 1. Dealership
            dealer = Dealership(
                dealer_id="DLR-PUN-01",
                name="Mahindra Sahyadri Auto Pune",
                city="Pune",
                state="Maharashtra",
                address="Wakad Flyover, Mumbai-Bangalore Highway, Pune 411057",
                phone_number="+912067891234",
                maps_url="https://maps.google.com/?q=Mahindra+Sahyadri+Pune",
                service_advisor_phone="+919822012345",
                total_service_bays=6
            )
            session.add(dealer)

            # 2. Customer
            cust = Customer(
                customer_id="CUST-101",
                full_name="Ramesh Sharma",
                phone_number="+919820198201",
                email="ramesh.sharma@example.in",
                preferred_language="hinglish",
                city="Pune",
                consent_dnd_scrubbed=True
            )
            session.add(cust)

            # 3. Vehicle
            veh = Vehicle(
                vin="VIN-MAH-SCN-2024-001",
                customer_id="CUST-101",
                registration_number="MH 12 RN 8921",
                model_name="Scorpio-N Z8L",
                fuel_type="Diesel",
                purchase_date=date(2024, 2, 15),
                current_odometer_km=20450,
                last_service_date=date(2025, 8, 10),
                last_service_mileage_km=10200,
                service_interval_months=6,
                service_interval_km=10000,
                service_due_type="20,000 KM PMS (2nd Free Service)",
                assigned_dealer_id="DLR-PUN-01"
            )
            session.add(veh)

            # 4. Catalog
            catalog = ServiceCostCatalog(
                model_name="Scorpio-N Z8L",
                service_type="PERIODIC_MAINTENANCE",
                mileage_interval_km=20000,
                estimated_parts_cost=2400.00,
                estimated_labor_cost=1200.00,
                engine_oil_cost=1600.00,
                tax_percentage=18.00,
                total_estimated_cost=6136.00,
                included_checklist=json.dumps([
                    "Engine Oil & Oil Filter Replacement (Mahindra Maximile)",
                    "Air Filter Cleaning and Inspection",
                    "Brake Pad & Rotor Thickness Check"
                ])
            )
            session.add(catalog)

            # 5. Slots
            now = datetime.now(timezone.utc)
            for i in range(1, 4):
                slot = ServiceSlot(
                    dealer_id="DLR-PUN-01",
                    slot_time=now + timedelta(days=1, hours=i),
                    bay_number=i,
                    is_booked=False,
                    locked_by_customer_id=None,
                    locked_until=None
                )
                session.add(slot)

            await session.commit()

    async def test_tool_get_customer_vehicle_profile_async(self):
        async with self.SessionLocal() as session:
            res = await execute_tool_call("get_customer_vehicle_profile", {"customer_id": "CUST-101"}, session)
            self.assertEqual(res["status"], "SUCCESS")
            data = res["data"]
            self.assertEqual(data["customer"]["full_name"], "Ramesh Sharma")
            self.assertEqual(data["vehicle"]["model_name"], "Scorpio-N Z8L")
            self.assertEqual(data["dealership"]["name"], "Mahindra Sahyadri Auto Pune")

    async def test_tool_get_service_cost_estimate_token_matching_async(self):
        async with self.SessionLocal() as session:
            # Test model parameter alias and "Mahindra Scorpio-N" prefix
            res = await execute_tool_call("get_service_cost_estimate", {"model": "Mahindra Scorpio-N"}, session)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["estimate"]["total_estimated_cost"], 6136.0)

    async def test_tool_check_available_slots_async(self):
        async with self.SessionLocal() as session:
            res = await execute_tool_call("check_available_slots", {"dealership_id": "DLR-PUN-01"}, session)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertGreater(res["available_slots_count"], 0)

    async def test_tool_hold_and_book_appointment_lifecycle_async(self):
        async with self.SessionLocal() as session:
            # 1. Hold slot 1
            hold_res = await execute_tool_call("hold_service_slot", {"slot_id": "slot_1", "customer_id": "CUST-101"}, session)
            self.assertTrue(hold_res["success"])
            self.assertEqual(hold_res["slot_id"], 1)

            # 2. Book slot 1
            book_res = await execute_tool_call("book_service_appointment", {
                "customer_id": "CUST-101",
                "slot_id": 1,
                "pickup_drop_required": "true",
                "pickup_address": "Baner, Pune",
                "customer_notes": "Wheel alignment check"
            }, session)
            self.assertTrue(book_res["success"])
            self.assertTrue(book_res["booking_reference"].startswith("#MND-PUN-"))
            self.assertEqual(book_res["status"], "CONFIRMED")
            self.assertTrue(book_res["pickup_drop_required"])

            # 3. Holding already booked slot should fail
            hold_again = await execute_tool_call("hold_service_slot", {"slot_id": 1, "customer_id": "CUST-102"}, session)
            self.assertFalse(hold_again["success"])

    async def test_tool_reschedule_reminder_async(self):
        async with self.SessionLocal() as session:
            cb_str = "2026-08-16T14:30:00Z"
            res = await execute_tool_call("reschedule_reminder", {
                "customer_id": "CUST-101",
                "callback_date_time": cb_str,
                "reason": "Customer in office meeting"
            }, session)
            self.assertTrue(res["success"])
            self.assertEqual(res["disposition"], "RESCHEDULED")

    async def test_tool_record_disposition_async(self):
        async with self.SessionLocal() as session:
            res = await execute_tool_call("record_customer_disposition", {
                "customer_id": "CUST-101",
                "disposition": "ALREADY_SERVICED",
                "notes": "Serviced last week at Mumbai dealer"
            }, session)
            self.assertTrue(res["success"])
            self.assertEqual(res["disposition"], "ALREADY_SERVICED")

    async def test_tool_transfer_to_advisor_async(self):
        async with self.SessionLocal() as session:
            res = await execute_tool_call("transfer_to_service_advisor", {
                "dealer_id": "DLR-PUN-01",
                "customer_id": "CUST-101",
                "reason": "Customer inquiry about 4x4 differential noise"
            }, session)
            self.assertTrue(res["success"])
            self.assertEqual(res["advisor_phone"], "+919822012345")

    async def test_originate_outbound_call_async(self):
        async with self.SessionLocal() as session:
            res = await campaign_service.originate_outbound_call(
                session=session,
                customer_id="CUST-101",
                target_phone="+919820198201",
                vin="VIN-MAH-SCN-2024-001"
            )
            self.assertTrue(res["success"])
            self.assertTrue(res["call_sid"].startswith("CA_"))
            self.assertEqual(res["customer_id"], "CUST-101")
            self.assertEqual(res["vehicle_model"], "Scorpio-N Z8L")


if __name__ == "__main__":
    unittest.main()
