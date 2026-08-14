variable "project_id" {
  description = "Google Cloud Platform Project ID or Project Number"
  type        = string
  default     = "1047195478355"
}

variable "region" {
  description = "GCP Deployment Region (for Vertex AI and Cloud Run)"
  type        = string
  default     = "us-central1"
}

variable "app_name" {
  description = "Application Service Name"
  type        = string
  default     = "voice-service-reminder"
}

variable "db_tier" {
  description = "Cloud SQL database instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "twilio_account_sid_secret" {
  description = "GCP Secret Manager secret ID or full resource path for Twilio Account SID"
  type        = string
  default     = "projects/1047195478355/secrets/TWILIO_ACCOUNT_SID"
}

variable "twilio_auth_token_secret" {
  description = "GCP Secret Manager secret ID or full resource path for Twilio Auth Token"
  type        = string
  default     = "projects/1047195478355/secrets/TWILIO_AUTH_TOKEN"
}

variable "twilio_phone_number" {
  description = "Twilio Phone Number"
  type        = string
  default     = "+13369154920"
}
