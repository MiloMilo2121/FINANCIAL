/**
 * Cloud Memorystore (Redis) for rate limiting and short-term caching.
 */

resource "google_redis_instance" "main" {
  name           = "financial-redis-${var.env}"
  project        = var.project_id
  region         = var.region
  tier           = var.tier
  memory_size_gb = var.env == "prod" ? 4 : 1

  redis_version = "REDIS_7_0"

  auth_enabled = true

  # Enable in-transit encryption
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 2
        minutes = 0
      }
    }
  }
}

output "host" {
  value = google_redis_instance.main.host
}

variable "project_id" { type = string }
variable "region"     { type = string }
variable "tier"       { type = string; default = "BASIC" }
variable "env"        { type = string }
