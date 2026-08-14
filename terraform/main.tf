terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "cloudtasks.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# 2. Cloud SQL PostgreSQL Instance
resource "google_sql_database_instance" "postgres_instance" {
  name             = "${var.app_name}-db-instance"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = var.db_tier
    ip_configuration {
      ipv4_enabled = true
    }
  }
  deletion_protection = false
  depends_on          = [google_project_service.enabled_apis]
}

resource "google_sql_database" "database" {
  name     = "service_reminder_db"
  instance = google_sql_database_instance.postgres_instance.name
}

resource "google_sql_user" "db_user" {
  name     = "reminder_admin"
  instance = google_sql_database_instance.postgres_instance.name
  password = "ChangeMeSecurely123!"
}

# 3. Cloud Pub/Sub Topics for Omnichannel Notifications & Dispositions
resource "google_pubsub_topic" "booking_confirmed" {
  name       = "booking-confirmed"
  depends_on = [google_project_service.enabled_apis]
}

resource "google_pubsub_topic" "call_dispositions" {
  name       = "call-dispositions"
  depends_on = [google_project_service.enabled_apis]
}

# 4. Service Account for Cloud Run with Vertex AI and Secret Manager Access
resource "google_service_account" "cloud_run_sa" {
  account_id   = "${var.app_name}-cr-sa"
  display_name = "Cloud Run Service Account for ${var.app_name}"
  depends_on   = [google_project_service.enabled_apis]
}

resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# 5. Cloud Run Service (Audio Gateway & WebSockets)
resource "google_cloud_run_v2_service" "voice_gateway" {
  name     = "${var.app_name}-gateway"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run_sa.email

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/${var.project_id}/${var.app_name}:latest"
      
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "GEMINI_MODEL"
        value = "gemini-2.0-flash-exp"
      }
      env {
        name  = "TWILIO_PHONE_NUMBER"
        value = var.twilio_phone_number
      }
      env {
        name  = "TWILIO_ACCOUNT_SID_SECRET"
        value = var.twilio_account_sid_secret
      }
      env {
        name  = "TWILIO_AUTH_TOKEN_SECRET"
        value = var.twilio_auth_token_secret
      }
      env {
        name = "TWILIO_ACCOUNT_SID"
        value_source {
          secret_key_ref {
            secret  = var.twilio_account_sid_secret
            version = "latest"
          }
        }
      }
      env {
        name = "TWILIO_AUTH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = var.twilio_auth_token_secret
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_project_iam_member.vertex_ai_user,
    google_project_iam_member.secret_accessor
  ]
}

# Allow unauthenticated invocations for Twilio Webhook and Browser UI
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.voice_gateway.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
