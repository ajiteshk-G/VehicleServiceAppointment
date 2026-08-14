# AI-Powered Voice Service Reminder System on GCP with Twilio Telephony & Vertex AI

An enterprise-grade, real-time multimodal conversational voice system designed for automotive customer service and service reminder concierge (supporting Mahindra Scorpio-N, XUV700, Thar, Swaraj 855 FE Tractors, and Scorpio Classic).

---

## 🌟 Key Architecture Highlights

1. **Zero Hardcoded Personas**:
   - 100% database-driven data layer (`schema.sql`).
   - Customer records, VINs, odometer readings, service interval rules, dealership workshop bay slots, and itemized pricing catalogs are loaded directly from the database.
   - Universal support for both **PostgreSQL** (Cloud SQL / Production) and **SQLite** (instant zero-dependency local testing).

2. **Real-time Audio Transcoding & Resampling Bridge** (`audio_transcoder.py`):
   - **Twilio PSTN Ingress**: Converts 8kHz G.711 $\mu$-law audio to 16kHz 16-bit Linear PCM for Vertex AI Gemini Live input.
   - **Vertex AI Gemini Live Output**: Downsamples 24kHz 16-bit Linear PCM to 8kHz and encodes to G.711 $\mu$-law for phone handsets.
   - Standalone fallback table algorithm ensures zero dependency issues across all Python versions (including Python 3.13+).

3. **Sub-40ms Barge-In Buffer Flushing**:
   - Streaming VAD detects customer speech interruptions in real time.
   - Immediately purges Python asyncio audio queues and sends Twilio `{"event": "clear", "streamSid": "..."}` to flush the phone handset speaker buffer instantly.

4. **Vertex AI Gemini 2.5 Multimodal Live API (ADC / IAM Auth)**:
   - Full-duplex bi-directional audio streaming over WebSocket (`wss://{location}-aiplatform.googleapis.com/...`).
   - Authenticates natively via **Google Application Default Credentials (ADC)** / OAuth2 bearer tokens — no API keys required.
   - Indic automotive persona ("Pooja from Mahindra Service Concierge") with natural Hindi / Hinglish / English code-switching.
   - 8 comprehensive domain tools with real-time latency tracking.

5. **Cloud Run Native & GCP Secret Manager Integration**:
   - **Cloud Run Native**: No ngrok or third-party tunnels needed. Automatically resolves dynamic webhook URLs and secure `wss://` Media Stream endpoints from Cloud Run request headers (`x-forwarded-proto`, `host`).
   - **GCP Secret Manager**: Automatically retrieves Twilio credentials from `projects/1047195478355/secrets/TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`.
   - **Twilio Caller ID**: Default phone number `+13369154920`.

6. **Dual Ingress Testing Modes**:
   - **Twilio PSTN Outbound Dialing**: Dial any real mobile phone number via Twilio Voice API from `+13369154920`.
   - **In-Browser WebRTC Mic Console**: Test conversational flows and domain tools directly using your computer microphone with zero phone credits required.

---

## 🛠️ 8 Comprehensive Domain Tools

| # | Tool Function | Purpose |
|---|---|---|
| 1 | `get_customer_vehicle_profile` | Retrieves customer profile, vehicle specs, odometer, and service history. |
| 2 | `get_service_cost_estimate` | Transparent pricing breakdown (parts, engine oil, labor, GST, and checklist). |
| 3 | `check_available_slots` | Queries dealership workshop bay slots for a given date. |
| 4 | `hold_service_slot` | Places an **atomic 180-second reservation hold** on a bay slot. |
| 5 | `book_service_appointment` | Confirms appointment, generates `#MND-PUN-8921` ref code, and dispatches SMS/WhatsApp. |
| 6 | `reschedule_reminder` | Schedules callback when customer is busy or driving. |
| 7 | `record_customer_disposition` | Logs CRM dispositions (`ALREADY_SERVICED`, `VEHICLE_SOLD`, `DECLINED`). |
| 8 | `transfer_to_service_advisor` | Warm transfer to senior human service advisor at the dealership. |

---

## 🚀 Quick Start Guide

### 1. Backend Setup

```bash
# Navigate to project root
cd /path/to/project

# Authenticate with GCP Vertex AI (Application Default Credentials)
gcloud auth application-default login

# Install dependencies
pip install -r backend/requirements.txt

# Run database migration & test data seed
python3 -m backend.app.seed_db

# Start the FastAPI server (Port 8000)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup (React + Vite Mission Control Console)

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000 in your browser
```

### 3. Environment Variables (`.env`)

```ini
# Google Cloud Platform & Vertex AI (ADC authentication, no API key needed)
GCP_PROJECT_ID=1047195478355
GCP_LOCATION=us-central1
GCP_REGION=us-central1
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_VOICE_NAME=Aoede

# Database (Leave as SQLite for local dev, or set PostgreSQL URI)
DATABASE_URL=sqlite+aiosqlite:///./service_reminder.db
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/servicedb

# Twilio Telephony Integration (Fetched automatically from Secret Manager or set directly)
TWILIO_ACCOUNT_SID_SECRET=projects/1047195478355/secrets/TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN_SECRET=projects/1047195478355/secrets/TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER=+13369154920
TWILIO_WHATSAPP_NUMBER=+14155238886

# Cloud Run / Host URL (Optional; automatically resolved from request headers when hosted on Cloud Run)
PUBLIC_BASE_URL=
```

---

## 🧪 Automated Testing

Run the test suites (runs out-of-the-box with zero 3rd-party dependencies):

```bash
# Run entire test suite
python3 -m unittest discover -s tests

# Or run individual standalone test modules
python3 tests/test_audio_transcoder.py
python3 tests/test_dms_service_edge_cases.py
python3 tests/test_tools_handler.py
python3 tests/test_vad.py
```

---

## ☁️ Google Cloud Deployment (Terraform & Cloud Run)

Deploy serverless infrastructure to GCP:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

The Cloud Run deployment automatically attaches a dedicated service account with `roles/aiplatform.user` and `roles/secretmanager.secretAccessor` permissions to access Vertex AI Gemini Live API and the Twilio secrets without hardcoded credentials.
