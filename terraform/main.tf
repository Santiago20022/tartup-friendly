terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "documentai.googleapis.com",
    "storage.googleapis.com",
    "firestore.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# Cloud Storage bucket for PDF uploads
resource "google_storage_bucket" "uploads" {
  name     = "${var.project_id}-ultrasound-uploads"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# Cloud Storage bucket for extracted images
resource "google_storage_bucket" "images" {
  name     = "${var.project_id}-ultrasound-images"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# Firestore database
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# Service account for Cloud Run
resource "google_service_account" "api_service" {
  account_id   = "vet-ultrasound-api"
  display_name = "VetUltrasound API Service Account"
}

# Grant permissions to service account
resource "google_project_iam_member" "api_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

resource "google_project_iam_member" "api_documentai" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.api_service.email}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "api" {
  name     = "vet-ultrasound-api"
  location = var.region

  template {
    service_account = google_service_account.api_service.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/${var.project_id}/vet-ultrasound-api:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_UPLOADS"
        value = google_storage_bucket.uploads.name
      }
      env {
        name  = "GCS_BUCKET_IMAGES"
        value = google_storage_bucket.images.name
      }
      env {
        name  = "DOCUMENTAI_PROCESSOR_ID"
        value = var.documentai_processor_id
      }
      env {
        name  = "DOCUMENTAI_LOCATION"
        value = var.documentai_location
      }
    }
  }

  depends_on = [
    google_project_service.apis,
    google_storage_bucket.uploads,
    google_storage_bucket.images,
    google_firestore_database.default,
  ]
}

# Allow unauthenticated access to Cloud Run (API handles its own auth)
resource "google_cloud_run_v2_service_iam_member" "public" {
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Outputs
output "api_url" {
  description = "URL of the deployed API"
  value       = google_cloud_run_v2_service.api.uri
}

output "uploads_bucket" {
  description = "Name of the uploads bucket"
  value       = google_storage_bucket.uploads.name
}

output "images_bucket" {
  description = "Name of the images bucket"
  value       = google_storage_bucket.images.name
}
