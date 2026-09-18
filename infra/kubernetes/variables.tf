variable "kubeconfig_path" {
  description = "Path to the kubeconfig used by the Kubernetes provider."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Explicit kubeconfig context. Null uses the active context."
  type        = string
  default     = null
  nullable    = true
}

variable "namespace" {
  description = "Namespace managed for the lab."
  type        = string
  default     = "release-lab"

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace))
    error_message = "namespace must be a valid lowercase Kubernetes name."
  }
}

variable "name" {
  description = "Application resource name."
  type        = string
  default     = "release-status"
}

variable "image" {
  description = "Immutable or locally loaded container image reference."
  type        = string
  default     = "cloud-release-reliability-lab:local"

  validation {
    condition     = length(trimspace(var.image)) > 0
    error_message = "image must not be blank."
  }
}

variable "image_pull_policy" {
  description = "Image pull policy; Never is useful for images loaded into Kind."
  type        = string
  default     = "IfNotPresent"

  validation {
    condition     = contains(["Always", "IfNotPresent", "Never"], var.image_pull_policy)
    error_message = "image_pull_policy must be Always, IfNotPresent, or Never."
  }
}

variable "replicas" {
  description = "Desired application replica count."
  type        = number
  default     = 2

  validation {
    condition     = var.replicas >= 1 && floor(var.replicas) == var.replicas
    error_message = "replicas must be a positive integer."
  }
}

variable "release_version" {
  description = "Release identifier exposed by the application."
  type        = string
  default     = "local"
}

variable "commit_sha" {
  description = "Source revision exposed by the application."
  type        = string
  default     = "unknown"
}

variable "environment" {
  description = "Logical deployment environment."
  type        = string
  default     = "local-kubernetes"
}

variable "force_not_ready" {
  description = "Controlled failure switch used only by release drills."
  type        = bool
  default     = false
}

