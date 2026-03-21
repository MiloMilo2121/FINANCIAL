output "gke_cluster_name" {
  value = module.gke.cluster_name
}

output "gke_cluster_endpoint" {
  value     = module.gke.cluster_endpoint
  sensitive = true
}

output "redis_host" {
  value     = module.redis.host
  sensitive = true
}

output "bigquery_dataset" {
  value = module.bigquery.dataset_id
}

output "raw_data_bucket" {
  value = google_storage_bucket.raw_data.name
}

output "models_bucket" {
  value = google_storage_bucket.model_artifacts.name
}
