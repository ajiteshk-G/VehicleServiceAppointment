output "cloud_run_service_url" {
  description = "Public URL for Cloud Run Voice Gateway"
  value       = google_cloud_run_v2_service.voice_gateway.uri
}

output "database_connection_name" {
  description = "Cloud SQL Instance Connection Name"
  value       = google_sql_database_instance.postgres_instance.connection_name
}

output "pubsub_booking_topic" {
  description = "Pub/Sub Topic for Booking Dispatches"
  value       = google_pubsub_topic.booking_confirmed.id
}
