/**
 * BigQuery dataset and tables for financial analytics.
 */

resource "google_bigquery_dataset" "financial" {
  dataset_id  = var.dataset_id
  project     = var.project_id
  location    = var.region
  description = "Financial Projection Platform analytics dataset"

  default_table_expiration_ms = null  # No auto-expiry

  labels = {
    env = var.env
  }
}

resource "google_bigquery_table" "prices" {
  dataset_id = google_bigquery_dataset.financial.dataset_id
  table_id   = "prices"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["asset", "source"]

  schema = file("${path.module}/schemas/prices.json")

  labels = { env = var.env }
}

resource "google_bigquery_table" "projections" {
  dataset_id = google_bigquery_dataset.financial.dataset_id
  table_id   = "projections"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "created_at"
  }

  clustering = ["asset", "model_tier"]

  schema = file("${path.module}/schemas/projections.json")

  labels = { env = var.env }
}

resource "google_bigquery_table" "sentiment_events" {
  dataset_id = google_bigquery_dataset.financial.dataset_id
  table_id   = "sentiment_events"
  project    = var.project_id

  time_partitioning {
    type  = "DAY"
    field = "analysis_timestamp"
  }

  labels = { env = var.env }
}

output "dataset_id" {
  value = google_bigquery_dataset.financial.dataset_id
}

variable "project_id" { type = string }
variable "region"     { type = string }
variable "dataset_id" { type = string }
variable "env"        { type = string }
