-- ==============================================================================
-- AI-Powered Automated Voice Service Reminder System
-- Database Schema (PostgreSQL & SQLite Compatible DDL)
-- ==============================================================================

-- 1. Dealerships & Service Centers
CREATE TABLE IF NOT EXISTS dealerships (
    dealer_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    maps_url TEXT,
    service_advisor_phone VARCHAR(20),
    total_service_bays INT DEFAULT 6
);

-- 2. Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    preferred_language VARCHAR(20) DEFAULT 'hinglish', -- 'en', 'hi', 'hinglish', 'mr'
    city VARCHAR(100),
    consent_dnd_scrubbed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Customer Vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    vin VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    registration_number VARCHAR(30) NOT NULL,
    model_name VARCHAR(100) NOT NULL, -- 'Scorpio-N Z8L', 'XUV700 AX7', 'Thar LX', 'Swaraj 855 FE'
    fuel_type VARCHAR(30) DEFAULT 'Diesel',
    purchase_date DATE NOT NULL,
    current_odometer_km INT NOT NULL,
    last_service_date DATE NOT NULL,
    last_service_mileage_km INT NOT NULL,
    service_interval_months INT DEFAULT 6,
    service_interval_km INT DEFAULT 10000,
    service_due_type VARCHAR(50) DEFAULT 'PERIODIC_MAINTENANCE', -- '20,000 KM PMS', '500 HRS TRACTOR SERVICE'
    assigned_dealer_id VARCHAR(50) REFERENCES dealerships(dealer_id)
);

-- 4. Transparent Service Pricing & Cost Catalog
CREATE TABLE IF NOT EXISTS service_cost_catalog (
    catalog_id INTEGER PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    mileage_interval_km INT NOT NULL,
    estimated_parts_cost NUMERIC(10, 2) NOT NULL,
    estimated_labor_cost NUMERIC(10, 2) NOT NULL,
    engine_oil_cost NUMERIC(10, 2) NOT NULL,
    tax_percentage NUMERIC(4, 2) DEFAULT 18.00,
    total_estimated_cost NUMERIC(10, 2) NOT NULL,
    included_checklist TEXT -- Stored as JSON array string for universal DB compatibility
);

-- 5. Dealership Workshop Bays & Slot Capacity
CREATE TABLE IF NOT EXISTS service_slots (
    slot_id INTEGER PRIMARY KEY,
    dealer_id VARCHAR(50) NOT NULL REFERENCES dealerships(dealer_id),
    slot_time TIMESTAMP WITH TIME ZONE NOT NULL,
    bay_number INT NOT NULL,
    is_booked BOOLEAN DEFAULT FALSE,
    locked_by_customer_id VARCHAR(50),
    locked_until TIMESTAMP WITH TIME ZONE -- Supports 180s atomic hold
);

-- 6. Confirmed Service Bookings
CREATE TABLE IF NOT EXISTS service_bookings (
    booking_id INTEGER PRIMARY KEY,
    booking_reference VARCHAR(50) UNIQUE NOT NULL, -- e.g. '#MND-PUN-8921'
    customer_id VARCHAR(50) NOT NULL REFERENCES customers(customer_id),
    vin VARCHAR(50) NOT NULL REFERENCES vehicles(vin),
    dealer_id VARCHAR(50) NOT NULL REFERENCES dealerships(dealer_id),
    slot_id INT REFERENCES service_slots(slot_id),
    slot_time TIMESTAMP WITH TIME ZONE NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    pickup_drop_required BOOLEAN DEFAULT FALSE,
    pickup_address TEXT,
    customer_notes TEXT,
    booking_status VARCHAR(50) DEFAULT 'CONFIRMED', -- 'CONFIRMED', 'CANCELLED', 'COMPLETED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Call Logs, Telemetry & Customer Dispositions
CREATE TABLE IF NOT EXISTS call_logs (
    call_id VARCHAR(100) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(customer_id),
    vin VARCHAR(50) REFERENCES vehicles(vin),
    channel VARCHAR(30) DEFAULT 'TWILIO_PSTN', -- 'TWILIO_PSTN' or 'WEBRTC_BROWSER'
    call_status VARCHAR(50) NOT NULL, -- 'ANSWERED', 'MACHINE_DETECTED', 'BUSY', 'NO_ANSWER', 'FAILED'
    disposition VARCHAR(50), -- 'BOOKED', 'RESCHEDULED', 'ALREADY_SERVICED', 'VEHICLE_SOLD', 'DECLINED', 'WARM_TRANSFERRED'
    callback_scheduled_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INT DEFAULT 0,
    transcript_json TEXT, -- Stored as JSON string
    tool_calls_json TEXT, -- Stored as JSON string
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
