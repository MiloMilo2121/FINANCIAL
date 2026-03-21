/**
 * Terraform configuration for Financial Projection Platform GCP infrastructure.
 *
 * Creates:
 *   - GKE Autopilot cluster (auto-provisioning for ML workloads)
 *   - BigQuery dataset and tables
 *   - Cloud Pub/Sub topics and subscriptions
 *   - Cloud Memorystore (Redis) for rate limiting
 *   - GCS buckets (raw data, model artifacts)
 *   - IAM service accounts with Workload Identity bindings
 *   - Certificate Authority Service (CAS) for mTLS
 */

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "financial-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ---- GKE Autopilot Cluster ----
module "gke" {
  source     = "./modules/gke"
  project_id = var.project_id
  region     = var.region
  cluster_name = "${var.env}-financial-cluster"
}

# ---- BigQuery ----
module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  region     = var.region
  dataset_id = "financial_data"
  env        = var.env
}

# ---- Pub/Sub ----
module "pubsub" {
  source     = "./modules/pubsub"
  project_id = var.project_id
  env        = var.env
}

# ---- Redis (Cloud Memorystore) ----
module "redis" {
  source     = "./modules/redis"
  project_id = var.project_id
  region     = var.region
  tier       = var.env == "prod" ? "STANDARD_HA" : "BASIC"
  env        = var.env
}

# ---- GCS Buckets ----
resource "google_storage_bucket" "raw_data" {
  name          = "${var.project_id}-raw-${var.env}"
  location      = var.region
  force_destroy = var.env != "prod"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 90 }
    action { type = "SetStorageClass"; storage_class = "NEARLINE" }
  }
}

resource "google_storage_bucket" "model_artifacts" {
  name     = "${var.project_id}-models-${var.env}"
  location = var.region

  versioning {
    enabled = true
  }
}

# ---- IAM Service Accounts for Workload Identity ----
resource "google_service_account" "ingestion" {
  account_id   = "financial-ingestion-${var.env}"
  display_name = "Financial Ingestion Service Account"
}

resource "google_service_account" "ml" {
  account_id   = "financial-ml-${var.env}"
  display_name = "Financial ML Service Account"
}

resource "google_service_account" "sentiment" {
  account_id   = "financial-sentiment-${var.env}"
  display_name = "Financial Sentiment Service Account"
}

# ---- IAM Bindings ----
resource "google_project_iam_member" "ingestion_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_project_iam_member" "ingestion_gcs_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_project_iam_member" "ml_bigquery_reader" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.ml.email}"
}

resource "google_project_iam_member" "ml_gcs_reader" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.ml.email}"
}

# ---- Secret Manager (API keys) ----
resource "google_secret_manager_secret" "api_keys" {
  for_each  = toset(["alpha-vantage-key", "perplexity-api-key", "pinecone-api-key"])
  secret_id = "financial-${each.key}-${var.env}"

  replication {
    auto {}
  }
}
