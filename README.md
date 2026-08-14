# 🚗 Mahindra & Swaraj AI Voice Service Concierge
### *Enterprise Voice AI for Automotive Periodic Maintenance Service (PMS) & Workshop Operations*

[![Vertex AI](https://img.shields.io/badge/Google_Cloud-Vertex_AI_Gemini_2.5_Live-4285F4?logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![Cloud Run](https://img.shields.io/badge/Serverless-Cloud_Run_Native-24C8F8?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Twilio](https://img.shields.io/badge/Telephony-Twilio_PSTN_Media_Streams-F22F46?logo=twilio&logoColor=white)](https://www.twilio.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_AsyncIO-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 📌 Executive Overview

The **Mahindra & Swaraj AI Voice Service Concierge** is a real-time, full-duplex conversational voice agent engineered for automotive OEMs and dealership networks. Powered by **Google Cloud Vertex AI Gemini 2.5 Live (`gemini-live-2.5-flash-native-audio`)** and **Twilio PSTN Telephony**, the system conducts proactive outbound service reminder calls, answers complex customer queries, transparently quotes service costs, reserves workshop bay slots, and schedules callbacks with sub-40ms conversational interruption (barge-in) latency.

### Key Capabilities
- **Multi-Brand OEM Support**: Pre-configured for Mahindra passenger vehicles (*Scorpio-N, XUV700, Thar, Scorpio Classic*) and farm equipment (*Swaraj 855 FE Tractor*).
- **Indic Natural Language Fluency**: Native code-switching between Hindi, Hinglish, English, Marathi, and Punjabi with feminine grammar ("Pooja").
- **Zero Hardcoding**: All customer profiles, vehicle telemetry, service schedules, dealership information, bay occupancy, and pricing catalogs are dynamically resolved from the database layer.
- **Enterprise Security**: Google Application Default Credentials (ADC) and OAuth2 bearer token authentication — no static API keys. Twilio credentials retrieved automatically from **GCP Secret Manager**.
- **Dual Ingress Testing**: Dial real mobile phones over Twilio PSTN or simulate calls in the browser using WebRTC / AudioWorklet with zero telephony credits.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Ingress["Customer Ingress Channels"]
        Phone["📱 Customer Phone (PSTN)"] -- 8kHz G.711u --o Twilio["Twilio Voice Media Stream (WSS)"]
        Browser["💻 Mission Control UI (WebRTC)"] -- 16/24kHz PCM --o WebAudio["Browser AudioWorklet (WSS)"]
    end

    subgraph CoreBridge["FastAPI Full-Duplex Audio Engine (Cloud Run)"]
        AudioBridge["AudioBridgeSession\n(/ws/twilio/stream & /ws/browser/audio)"]
        Transcoder["Audio Transcoder\n(8kHz G.711u <--> 16/24kHz PCM16)"]
        VAD["Streaming VAD & Energy Tracker\n(Sub-40ms Interruption Detection)"]
        BargeIn["Barge-in Buffer Flusher\n(Sends Twilio 'clear' event)"]
        
        AudioBridge <--> Transcoder
        AudioBridge --> VAD
        VAD --> BargeIn
    end

    subgraph AIPlatform["Google Cloud Vertex AI"]
        GeminiLive["Gemini 2.5 Live Multimodal API\n(gemini-live-2.5-flash-native-audio)"]
        AuthADC["OAuth2 Bearer Token / ADC\n(roles/aiplatform.user)"]
        
        AuthADC -.-> GeminiLive
        AudioBridge <== Bidirectional PCM16 WSS ==> GeminiLive
    end

    subgraph BusinessLogic["Domain Tools & DMS Database"]
        ToolsHandler["Agent Tools Handler\n(9 Domain Function Tools)"]
        DMSService["DMS & Bay Scheduling Service"]
        DB[(PostgreSQL / SQLite Database\nDealerships | Customers | Slots | Catalog)]
        Notification["SMS / WhatsApp Service"]
        
        GeminiLive -- Tool Call / Response --> ToolsHandler
        ToolsHandler --> DMSService
        DMSService <--> DB
        DMSService --> Notification
    end

    subgraph Observability["Live Telemetry & Management"]
        TelemetryWS["Telemetry WebSocket (/ws/telemetry)"]
        UIConsole["Mission Control UI\n(Waveform | Transcripts | Bay Grid | Call History)"]
        
        AudioBridge -. Live State Events .-> TelemetryWS
        TelemetryWS -. Broadcast .-> UIConsole
    end
```

---

## 🌟 Core Technical Highlights

### 1. Full-Duplex Native Audio Streaming (`live_gemini_client.py`)
- Direct bidirectional streaming over WebSocket with `wss://{location}-aiplatform.googleapis.com/.../BidiGenerateContent`.
- Authenticates using Google Application Default Credentials (ADC) or OAuth2 bearer tokens refreshed automatically at runtime.
- Employs the `Aoede` voice profile with natural Indic warmth, tone, and pacing.

### 2. High-Performance Audio Transcoding Bridge (`audio_transcoder.py`)
- Converts **8kHz G.711 $\mu$-law** from PSTN phone networks to **16kHz 16-bit Linear PCM** for Gemini Live ingestion.
- Resamples **24kHz 16-bit Linear PCM** output from Gemini Live to **8kHz G.711 $\mu$-law** for phone handsets.
- Zero external C-library dependencies — utilizes accelerated `audioop` / `audioop-lts` with an optimized precomputed lookup table fallback compatible across all Python runtimes (including Python 3.13+).

### 3. Sub-40ms Conversational Barge-In (`vad.py` & `audio_bridge.py`)
- Real-time energy and RMS analysis detects customer speech interruptions during AI playback.
- Instantly cancels in-flight audio playback queues, drops pending audio frames, and sends an atomic `{"event": "clear", "streamSid": "..."}` frame to Twilio to flush the physical phone handset speaker buffer in under 40ms.

### 4. Intent-Driven Tool Calling & Polite Closing Protocol (`prompts.py`)
- **Strict Intent Guardrails**: The agent actively listens and invokes only the exact matching tool (e.g., `get_service_cost_estimate` only when pricing is requested; `check_available_slots` only when dates are requested).
- **Polite Closing Protocol**: The agent never abruptly hangs up. It confirms whether the customer needs any additional assistance (*"Kya main aapki kisi aur cheez mein sahayata kar sakti hoon?"*) and only invokes `end_call` upon explicit customer affirmation.

---

## 🛠️ Domain Tools Reference

The system provides 9 function declarations to the Gemini 2.5 Live model:

| # | Tool Function | Purpose | Database Interaction |
|---|---|---|---|
| 1 | `get_customer_vehicle_profile` | Retrieves dynamic customer details, vehicle specification, odometer, and past service history. | `customers`, `vehicles`, `dealerships` |
| 2 | `get_service_cost_estimate` | Itemized price quotation (Parts, Engine Oil, Labor, 18% GST, and checklist). | `service_cost_catalog` |
| 3 | `check_available_slots` | Queries open workshop bay appointment slots for a dealership and date. | `service_slots` |
| 4 | `hold_service_slot` | Places an optimistic **180-second reservation hold** on a bay slot during call confirmation. | `service_slots` (`locked_until`) |
| 5 | `book_service_appointment` | Finalizes booking, generates unique reference (e.g. `#MND-PUN-1793`), and sends SMS/WhatsApp. | `service_bookings`, `service_slots` |
| 6 | `reschedule_reminder` | Schedules a follow-up callback date/time when customer is busy, in a meeting, or driving. | `call_logs`, `vehicles` |
| 7 | `record_customer_disposition` | Logs CRM outcome dispositions (`ALREADY_SERVICED`, `DECLINED`). | `call_logs`, `vehicles` |
| 8 | `transfer_to_service_advisor` | Warm transfer to the human Service Advisor at the dealership. | `dealerships` (`service_advisor_phone`) |
| 9 | `end_call` | Concludes call politely and triggers graceful telephony / WebRTC teardown. | `call_logs` (`duration_seconds`) |

---

## 📊 Canonical Call Dispositions & Outcomes

All outbound calls and customer interactions are normalized into 5 canonical outcomes across the database, APIs, and dashboard:

| Badge | Outcome Code | Trigger Condition | Follow-up Action |
|---|---|---|---|
| 🟢 | `BOOKED` | Customer confirmed a service appointment date and workshop bay slot. | Instant SMS/WhatsApp confirmation dispatched. |
| 🟡 | `RESCHEDULED` | Customer requested a callback at a later time (e.g., in a meeting or driving). | Scheduled for automated follow-up dialer batch. |
| 🔵 | `TRANSFERRED` | Customer required specialized mechanical consultation or escalation. | Transferred to dealership Service Advisor phone. |
| ⚪ | `ALREADY_SERVICED` | Vehicle was recently serviced at another dealership or workshop. | Service reminder postponed by 6 months / 10,000 km. |
| 🔴 | `DECLINED` | Vehicle sold, customer not interested, or opted out. | Marked inactive in campaign dialer list. |

---

## 🖥️ Mission Control UI Console

The application includes an interactive split-screen Mission Control UI accessible at `http://localhost:8080` (or the Cloud Run service URL):

```
┌───────────────────────────────────┬───────────────────────────────────┬───────────────────────────────────┐
│       🎙️ Voice & Audio Stream     │     🧠 AI Reasoning & Tools Feed  │      🏢 DMS Workshop Bay Monitor  │
├───────────────────────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ • Live Audio Waveform (60 FPS)    │ • Intent & Thought Tracing        │ • 3D Workshop Bay Occupancy Grid  │
│ • Volume RMS Level Meter          │ • Real-time Tool Call Telemetry   │ • Live Slot Lock Status (180s)    │
│ • Dual Mode: Twilio Dial / Mic    │ • Execution Latency Benchmarks    │ • Dynamic Customer Selector       │
│ • Streaming Transcript with VAD   │ • Function Argument Payloads      │ • Instant Slot Booking Form       │
└───────────────────────────────────┴───────────────────────────────────┴───────────────────────────────────┘
│                                  📋 Call History & Transcripts Tab                                        │
│  • Search & Filter by 5 Canonical Outcomes (Booked, Rescheduled, Transferred, Serviced, Declined)        │
│  • Formatted Indian Standard Time (IST) Timestamps                                                        │
│  • Single-Line Turn Consolidator & Detailed Turn-by-Turn Modal Dialog                                    │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Directory Structure

```
├── Dockerfile                         # Root multi-stage Docker build for Cloud Run
├── README.md                          # Enterprise system documentation
├── backend/
│   ├── Dockerfile                     # Container definition
│   ├── requirements.txt               # Backend Python dependencies
│   ├── schema.sql                     # Relational database schema
│   └── app/
│       ├── config.py                  # Environment config & GCP Secret Manager integration
│       ├── database.py                # Async SQLAlchemy engine (SQLite / PostgreSQL)
│       ├── main.py                    # FastAPI application, REST endpoints, & WebSockets
│       ├── models.py                  # SQLAlchemy ORM models
│       ├── seed_db.py                 # Multi-dealership seed script with slot generator
│       ├── static_index.html          # Mission Control UI Console (Tailwind + Lucide + WebAudio)
│       ├── agents/
│       │   ├── prompts.py             # Indic persona builder & feminine Hindi/Hinglish instructions
│       │   ├── tools_declaration.py   # Gemini 2.5 Live function declarations
│       │   └── tools_handler.py       # Asynchronous tool execution & latency instrumentation
│       ├── core/
│       │   ├── audio_bridge.py        # Bidirectional audio session router & hangup scheduler
│       │   ├── audio_transcoder.py    # G.711u <-> PCM16 transcoder & resampler
│       │   ├── live_gemini_client.py  # Vertex AI Gemini 2.5 Live WebSocket client
│       │   └── vad.py                 # Streaming Voice Activity Detection & energy analyzer
│       └── services/
│           ├── campaign_service.py    # Batch campaign dialer simulator
│           ├── dms_service.py         # Workshop scheduling, slot reservation, & pricing engine
│           └── notification_service.py# SMS & WhatsApp confirmation dispatcher
├── frontend/                          # Optional standalone React + Vite UI
│   ├── package.json
│   ├── vite.config.js
│   └── src/
├── terraform/                         # Infrastructure-as-Code for GCP
│   ├── main.tf                        # Cloud Run, IAM roles, & Secret Manager configuration
│   ├── variables.tf                   # Terraform input variables
│   └── outputs.tf                     # Cloud Run service URL output
└── tests/                             # Automated Test Suite (73 Tests)
    ├── test_async_tools_and_dms.py
    ├── test_audio_edge_cases.py
    ├── test_audio_transcoder.py
    ├── test_config_and_secrets.py
    ├── test_database_seed.py
    ├── test_dms_service_edge_cases.py
    ├── test_prompts_and_declarations.py
    ├── test_standalone_tools.py
    ├── test_standalone_transcoder.py
    ├── test_tools_handler.py
    ├── test_vad.py
    └── test_vertex_live_client.py
```

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `1047195478355` | Google Cloud Project ID or Number |
| `GCP_LOCATION` | `us-central1` | Vertex AI Region (`us-central1`, `asia-south1`) |
| `GEMINI_MODEL` | `gemini-live-2.5-flash-native-audio` | Vertex AI Live Multimodal Audio Model |
| `GEMINI_VOICE_NAME` | `Aoede` | Gemini voice profile (`Aoede`, `Puck`, `Charon`, `Kore`, `Fenrir`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./service_reminder.db` | SQLAlchemy Async Database URI (PostgreSQL or SQLite) |
| `TWILIO_PHONE_NUMBER` | `+13369154920` | Twilio Outbound Caller ID phone number |
| `TWILIO_ACCOUNT_SID_SECRET` | `projects/1047195478355/secrets/TWILIO_ACCOUNT_SID` | GCP Secret Manager secret path for Twilio SID |
| `TWILIO_AUTH_TOKEN_SECRET` | `projects/1047195478355/secrets/TWILIO_AUTH_TOKEN` | GCP Secret Manager secret path for Twilio Auth Token |
| `PUBLIC_BASE_URL` | *(Dynamic)* | Base URL for webhooks (auto-resolved from Cloud Run headers) |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud`) authenticated via Application Default Credentials:
  ```bash
  gcloud auth application-default login
  ```

### 2. Installation & Database Setup
```bash
# Clone the repository
git clone https://github.com/ajiteshk-G/VehicleServiceAppointment.git
cd VehicleServiceAppointment

# Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Populate initial dealerships, vehicles, customers, and bay slots
python3 -m backend.app.seed_db
```

### 3. Run Automated Tests
Execute the comprehensive test suite (all 73 automated tests):
```bash
python3 -m unittest discover tests
```

### 4. Launch Local Development Server
```bash
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser to access the Mission Control UI.

---

## ☁️ Cloud Run Deployment

Deploy the container directly to Google Cloud Run:

```bash
gcloud run deploy vehicle-service-reminder \
  --source . \
  --project mb-poc-352009 \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=mb-poc-352009,GCP_LOCATION=us-central1,GEMINI_MODEL=gemini-live-2.5-flash-native-audio,TWILIO_PHONE_NUMBER=+13369154920,TWILIO_ACCOUNT_SID_SECRET=projects/1047195478355/secrets/TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN_SECRET=projects/1047195478355/secrets/TWILIO_AUTH_TOKEN
```

### Terraform Infrastructure as Code
Alternatively, deploy via Terraform:
```bash
cd terraform
terraform init
terraform plan -var="project_id=mb-poc-352009" -var="region=us-central1"
terraform apply
```

---

## 🌐 API & WebSocket Endpoints

| Method / Protocol | Path | Purpose |
|---|---|---|
| `GET` | `/` | Serves the interactive Mission Control UI Console. |
| `GET` | `/health` | Health probe returning database, Twilio, and Vertex AI status. |
| `GET` | `/api/customers` | Lists all customer profiles with vehicle and dealership associations. |
| `GET` | `/api/dealerships` | Lists dealerships, contact details, and total bay capacities. |
| `GET` | `/api/slots?dealer_id=...` | Retrieves available and locked workshop bay slots. |
| `GET` | `/api/call-logs` | Retrieves call history, IST timestamps, dispositions, and transcripts. |
| `POST` | `/api/telephony/originate-call` | Initiates an outbound PSTN phone call via Twilio. |
| `POST` | `/twiml` | Serves TwiML instruction connecting the call to `/ws/twilio/stream`. |
| `WebSocket` | `/ws/twilio/stream` | Bidirectional 8kHz G.711 $\mu$-law audio stream with Twilio. |
| `WebSocket` | `/ws/browser/audio` | Bidirectional 16kHz/24kHz PCM audio stream with in-browser mic. |
| `WebSocket` | `/ws/telemetry` | Real-time event stream broadcasting transcripts, audio RMS, and tool execution. |

---

## 📄 License
This project is licensed under the Apache 2.0 License.

