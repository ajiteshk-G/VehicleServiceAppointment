"""Database Seeding Script - Populates test dealerships, customers, vehicles, pricing, and workshop bay slots."""

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
try:
    from sqlalchemy import select, delete, and_
except ImportError:
    select = delete = and_ = None

from backend.app.database import AsyncSessionLocal, init_db
from backend.app.models import Dealership, Customer, Vehicle, ServiceCostCatalog, ServiceSlot, ServiceBooking

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_db")


DEALERSHIPS = [
    {
        "dealer_id": "DLR-PUN-01",
        "name": "Mahindra Sahyadri Auto Pune",
        "city": "Pune",
        "state": "Maharashtra",
        "address": "Wakad Flyover, Mumbai-Bangalore Highway, Pune 411057",
        "phone_number": "+912067891234",
        "maps_url": "https://maps.google.com/?q=Mahindra+Sahyadri+Pune",
        "service_advisor_phone": "+919822012345",
        "total_service_bays": 6,
    },
    {
        "dealer_id": "DLR-BLR-01",
        "name": "Mahindra Sireesh Auto Bengaluru",
        "city": "Bengaluru",
        "state": "Karnataka",
        "address": "Marathahalli Outer Ring Rd, Bengaluru 560037",
        "phone_number": "+918045678901",
        "maps_url": "https://maps.google.com/?q=Sireesh+Auto+Bengaluru",
        "service_advisor_phone": "+919845012345",
        "total_service_bays": 8,
    },
    {
        "dealer_id": "DLR-CHD-01",
        "name": "Swaraj Agro Tractors Chandigarh",
        "city": "Chandigarh",
        "state": "Punjab",
        "address": "GT Road, Mohali, Punjab 160055",
        "phone_number": "+911722894567",
        "maps_url": "https://maps.google.com/?q=Swaraj+Agro+Mohali",
        "service_advisor_phone": "+919814012345",
        "total_service_bays": 4,
    },
    {
        "dealer_id": "DLR-DEL-01",
        "name": "Mahindra Koncept Automobiles New Delhi",
        "city": "New Delhi",
        "state": "Delhi",
        "address": "B-1/E-24, Mohan Cooperative Industrial Estate, Mathura Road, New Delhi 110044",
        "phone_number": "+911145678901",
        "maps_url": "https://maps.google.com/?q=Mahindra+Koncept+Automobiles+New+Delhi",
        "service_advisor_phone": "+919811012345",
        "total_service_bays": 8,
    },
]

CUSTOMERS = [
    {
        "customer_id": "CUST-101",
        "full_name": "Ramesh Sharma",
        "phone_number": "+919820198201",
        "email": "ramesh.sharma@example.in",
        "preferred_language": "hinglish",
        "city": "Pune",
        "consent_dnd_scrubbed": True,
    },
    {
        "customer_id": "CUST-102",
        "full_name": "Priya Patel",
        "phone_number": "+919876543210",
        "email": "priya.patel@example.in",
        "preferred_language": "en",
        "city": "Bengaluru",
        "consent_dnd_scrubbed": True,
    },
    {
        "customer_id": "CUST-103",
        "full_name": "Vikram Singh",
        "phone_number": "+919811223344",
        "email": "vikram.singh@example.in",
        "preferred_language": "hi",
        "city": "New Delhi",
        "consent_dnd_scrubbed": True,
    },
    {
        "customer_id": "CUST-104",
        "full_name": "Gurpreet Singh",
        "phone_number": "+919814556677",
        "email": "gurpreet.singh@example.in",
        "preferred_language": "hinglish",
        "city": "Chandigarh",
        "consent_dnd_scrubbed": True,
    },
    {
        "customer_id": "CUST-105",
        "full_name": "Anita Deshmukh",
        "phone_number": "+919890112233",
        "email": "anita.deshmukh@example.in",
        "preferred_language": "mr",
        "city": "Pune",
        "consent_dnd_scrubbed": True,
    },
]

VEHICLES = [
    {
        "vin": "VIN-MAH-SCN-2024-001",
        "customer_id": "CUST-101",
        "registration_number": "MH 12 RN 8921",
        "model_name": "Scorpio-N Z8L",
        "fuel_type": "Diesel",
        "purchase_date": date(2024, 2, 15),
        "current_odometer_km": 20450,
        "last_service_date": date(2025, 8, 10),
        "last_service_mileage_km": 10200,
        "service_interval_months": 6,
        "service_interval_km": 10000,
        "service_due_type": "20,000 KM PMS (2nd Free Service)",
        "assigned_dealer_id": "DLR-PUN-01",
    },
    {
        "vin": "VIN-MAH-XUV-2023-088",
        "customer_id": "CUST-102",
        "registration_number": "MH 14 TC 4512",
        "model_name": "XUV700 AX7",
        "fuel_type": "Petrol",
        "purchase_date": date(2023, 5, 20),
        "current_odometer_km": 30800,
        "last_service_date": date(2025, 6, 15),
        "last_service_mileage_km": 20100,
        "service_interval_months": 6,
        "service_interval_km": 10000,
        "service_due_type": "30,000 KM PMS (Major Service)",
        "assigned_dealer_id": "DLR-BLR-01",
    },
    {
        "vin": "VIN-MAH-THR-2024-512",
        "customer_id": "CUST-103",
        "registration_number": "DL 3C AB 9012",
        "model_name": "Thar LX",
        "fuel_type": "Diesel",
        "purchase_date": date(2024, 3, 10),
        "current_odometer_km": 10120,
        "last_service_date": date(2024, 4, 12),
        "last_service_mileage_km": 1050,
        "service_interval_months": 6,
        "service_interval_km": 10000,
        "service_due_type": "10,000 KM PMS (1st Paid Service)",
        "assigned_dealer_id": "DLR-DEL-01",
    },
    {
        "vin": "VIN-SWR-855-2022-771",
        "customer_id": "CUST-104",
        "registration_number": "PB 11 AG 3321",
        "model_name": "Swaraj 855 FE",
        "fuel_type": "Diesel",
        "purchase_date": date(2022, 10, 5),
        "current_odometer_km": 480,
        "last_service_date": date(2023, 11, 20),
        "last_service_mileage_km": 250,
        "service_interval_months": 12,
        "service_interval_km": 250,
        "service_due_type": "500 HRS Periodic Tractor Maintenance",
        "assigned_dealer_id": "DLR-CHD-01",
    },
    {
        "vin": "VIN-MAH-SCL-2023-119",
        "customer_id": "CUST-105",
        "registration_number": "MH 02 ER 6654",
        "model_name": "Scorpio Classic S11",
        "fuel_type": "Diesel",
        "purchase_date": date(2023, 1, 18),
        "current_odometer_km": 40200,
        "last_service_date": date(2025, 7, 2),
        "last_service_mileage_km": 30000,
        "service_interval_months": 6,
        "service_interval_km": 10000,
        "service_due_type": "40,000 KM PMS",
        "assigned_dealer_id": "DLR-PUN-01",
    },
]

PRICING_CATALOG = [
    {
        "model_name": "Scorpio-N Z8L",
        "service_type": "PERIODIC_MAINTENANCE",
        "mileage_interval_km": 20000,
        "estimated_parts_cost": 2400.00,
        "estimated_labor_cost": 1200.00,
        "engine_oil_cost": 1600.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 6136.00,
        "included_checklist": json.dumps([
            "Engine Oil & Oil Filter Replacement (Mahindra Maximile)",
            "Air Filter Cleaning and Inspection",
            "Brake Pad & Rotor Thickness Check",
            "Coolant & Brake Fluid Top-up",
            "Underbody & Suspension Nut Torquing",
            "Battery Health & Alternator Voltage Check",
            "Tyre Rotation & Digital Pressure Balancing"
        ]),
    },
    {
        "model_name": "Scorpio-N Z8L",
        "service_type": "GENERAL_CHECKUP",
        "mileage_interval_km": 10000,
        "estimated_parts_cost": 0.00,
        "estimated_labor_cost": 650.00,
        "engine_oil_cost": 0.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 767.00,
        "included_checklist": json.dumps([
            "40-Point Comprehensive Vehicle Inspection",
            "Windshield Washer & Brake Fluid Top-up",
            "Brake Inspection & Cleaning",
            "Complimentary Body Wash & Vacuum"
        ]),
    },
    {
        "model_name": "XUV700 AX7",
        "service_type": "PERIODIC_MAINTENANCE",
        "mileage_interval_km": 30000,
        "estimated_parts_cost": 3800.00,
        "estimated_labor_cost": 1500.00,
        "engine_oil_cost": 2100.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 8732.00,
        "included_checklist": json.dumps([
            "Full Synthetic Engine Oil Replacement",
            "Oil Filter, Fuel Filter & Cabin AC Filter Replacement",
            "Front & Rear Disc Brake Caliper Service",
            "ADAS Camera & Radar Sensor Calibration Check",
            "Software ECU Diagnostics & Health Report",
            "Wheel Alignment & Dynamic Balancing"
        ]),
    },
    {
        "model_name": "Thar LX",
        "service_type": "PERIODIC_MAINTENANCE",
        "mileage_interval_km": 10000,
        "estimated_parts_cost": 1800.00,
        "estimated_labor_cost": 950.00,
        "engine_oil_cost": 1500.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 5015.00,
        "included_checklist": json.dumps([
            "Engine Oil & Filter Replacement",
            "4x4 Transfer Case & Differential Fluid Inspection",
            "Suspension Greasing & Bushing Health Check",
            "High-Flow Air Filter Cleaning",
            "Underbody Off-Road Armor & Skid Plate Inspection"
        ]),
    },
    {
        "model_name": "Swaraj 855 FE",
        "service_type": "PERIODIC_MAINTENANCE",
        "mileage_interval_km": 500,
        "estimated_parts_cost": 1400.00,
        "estimated_labor_cost": 600.00,
        "engine_oil_cost": 2200.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 4956.00,
        "included_checklist": json.dumps([
            "Heavy Duty Diesel Engine Oil Replacement (7.5L)",
            "Fuel Filter (Primary & Secondary) Replacement",
            "Hydraulic Oil Strainer Cleaning",
            "Air Cleaner Oil Bath Cleaning & Refill",
            "Clutch & Brake Pedal Free Play Adjustment",
            "Fan Belt Tension Adjustment"
        ]),
    },
    {
        "model_name": "Scorpio Classic S11",
        "service_type": "PERIODIC_MAINTENANCE",
        "mileage_interval_km": 40000,
        "estimated_parts_cost": 2200.00,
        "estimated_labor_cost": 1100.00,
        "engine_oil_cost": 1600.00,
        "tax_percentage": 18.00,
        "total_estimated_cost": 5782.00,
        "included_checklist": json.dumps([
            "Engine Oil & Oil Filter Replacement",
            "Diesel Fuel Filter Element Replacement",
            "Brake & Clutch Fluid Replacement",
            "Suspension Leaf Spring Greasing",
            "Drive Belt & Idler Pulley Check"
        ]),
    },
]


async def seed_database():
    """Seeds the database with foundational records."""
    await init_db()

    async with AsyncSessionLocal() as session:
        logger.info("Checking existing records in database...")

        # Sync / Upsert dealerships
        for d in DEALERSHIPS:
            res = await session.execute(select(Dealership).where(Dealership.dealer_id == d["dealer_id"]))
            existing = res.scalars().first()
            if not existing:
                session.add(Dealership(**d))
            else:
                for k, v in d.items():
                    setattr(existing, k, v)
        await session.commit()
        logger.info(f"Synchronized {len(DEALERSHIPS)} dealerships.")

        # Sync / Upsert customers
        for c in CUSTOMERS:
            res = await session.execute(select(Customer).where(Customer.customer_id == c["customer_id"]))
            existing = res.scalars().first()
            if not existing:
                session.add(Customer(**c))
            else:
                for k, v in c.items():
                    setattr(existing, k, v)
        await session.commit()
        logger.info(f"Synchronized {len(CUSTOMERS)} customers.")

        # Sync / Upsert vehicles
        for v in VEHICLES:
            res = await session.execute(select(Vehicle).where(Vehicle.vin == v["vin"]))
            existing = res.scalars().first()
            if not existing:
                session.add(Vehicle(**v))
            else:
                for k, val in v.items():
                    setattr(existing, k, val)
        await session.commit()
        logger.info(f"Synchronized {len(VEHICLES)} vehicles.")

        # Check pricing catalog
        res = await session.execute(select(ServiceCostCatalog))
        existing_catalog = res.scalars().all()
        if not existing_catalog:
            logger.info("Seeding service pricing catalog...")
            for p in PRICING_CATALOG:
                session.add(ServiceCostCatalog(**p))
            await session.commit()
            logger.info(f"Seeded {len(PRICING_CATALOG)} catalog items.")
        else:
            logger.info(f"Found {len(existing_catalog)} catalog items already seeded.")

        # Seed workshop bay slots for the next 7 days for any dealer missing slots
        now = datetime.now(timezone.utc)
        start_date = now.date()
        slot_times = [
            (9, 0),
            (10, 0),
            (11, 30),
            (14, 0),
            (15, 30),
            (17, 0),
        ]

        slot_count = 0
        for d in DEALERSHIPS:
            dealer_id = d["dealer_id"]
            total_bays = d["total_service_bays"]
            res = await session.execute(
                select(ServiceSlot).where(
                    and_(
                        ServiceSlot.dealer_id == dealer_id,
                        ServiceSlot.slot_time >= now
                    )
                ).limit(1)
            )
            if not res.scalars().first():
                for day_offset in range(1, 8):
                    current_day = start_date + timedelta(days=day_offset)
                    for bay in range(1, total_bays + 1):
                        for hour, minute in slot_times:
                            slot_dt = datetime(
                                current_day.year,
                                current_day.month,
                                current_day.day,
                                hour,
                                minute,
                                tzinfo=timezone.utc
                            )
                            is_booked = (day_offset == 1 and bay == 1 and hour == 10)
                            slot = ServiceSlot(
                                dealer_id=dealer_id,
                                slot_time=slot_dt,
                                bay_number=bay,
                                is_booked=is_booked,
                                locked_by_customer_id=None,
                                locked_until=None
                            )
                            session.add(slot)
                            slot_count += 1

        if slot_count > 0:
            await session.commit()
            logger.info(f"Successfully generated {slot_count} workshop bay slots.")
        else:
            logger.info("Found upcoming service slots already present for all dealerships.")

    logger.info("Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_database())
