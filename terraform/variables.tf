variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "documentai_processor_id" {
  description = "Document AI processor ID"
  type        = string
}

variable "documentai_location" {
  description = "Document AI processor location"
  type        = string
  default     = "us"
}
