/**
 * Cloud Pub/Sub topics and subscriptions.
 */

resource "google_pubsub_topic" "market_events" {
  name    = "market-events"
  project = var.project_id

  message_storage_policy {
    allowed_persistence_regions = ["us-central1"]
  }
}

resource "google_pubsub_topic" "sentiment_events" {
  name    = "sentiment-events"
  project = var.project_id
}

resource "google_pubsub_subscription" "market_events_etl" {
  name    = "market-events-etl-sub"
  topic   = google_pubsub_topic.market_events.name
  project = var.project_id

  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"  # 24 hours

  # Exponential backoff retry policy
  retry_policy {
    minimum_backoff = "2s"
    maximum_backoff = "300s"
  }
}

resource "google_pubsub_subscription" "market_events_sentiment" {
  name    = "market-events-sentiment-sub"
  topic   = google_pubsub_topic.market_events.name
  project = var.project_id

  ack_deadline_seconds       = 300  # 5 min for Perplexity API calls
  message_retention_duration = "86400s"

  retry_policy {
    minimum_backoff = "5s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "sentiment_events_ml" {
  name    = "sentiment-events-ml-sub"
  topic   = google_pubsub_topic.sentiment_events.name
  project = var.project_id

  ack_deadline_seconds = 60
}

variable "project_id" { type = string }
variable "env"        { type = string }
