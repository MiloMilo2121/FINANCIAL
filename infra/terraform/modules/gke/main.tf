/**
 * GKE Autopilot cluster module.
 * Autopilot auto-provisions node pools based on pod resource requests,
 * ideal for variable ML workloads (GPU burst for inference).
 */

resource "google_container_cluster" "main" {
  name     = var.cluster_name
  location = var.region
  project  = var.project_id

  # Enable Autopilot (replaces node pool management)
  enable_autopilot = true

  # Workload Identity: allows pods to use GSA via KSA binding
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Private cluster: nodes have no external IPs
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Enable Dataplane V2 (eBPF-based networking, required for mTLS network policies)
  datapath_provider = "ADVANCED_DATAPATH"

  # Binary Authorization: SLSA Level 3 supply chain security
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }

  release_channel {
    channel = "REGULAR"
  }
}

output "cluster_name" {
  value = google_container_cluster.main.name
}

output "cluster_endpoint" {
  value = google_container_cluster.main.endpoint
}
