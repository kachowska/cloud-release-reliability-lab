variable "name_prefix" {
  description = "Globally safe lowercase prefix used for the lab's Azure resources."
  type        = string
  default     = "releaselabdemo"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,18}[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be 6-20 lowercase letters, numbers, or hyphens."
  }
}

variable "location" {
  description = "Azure region for the configuration-only target."
  type        = string
  default     = "polandcentral"
}

variable "node_vm_size" {
  description = "Illustrative system-pool VM size; verify quota and cost before any apply."
  type        = string
  default     = "Standard_B2s"
}

variable "kubernetes_version" {
  description = "Optional AKS Kubernetes version; null asks Azure for the default."
  type        = string
  default     = null
  nullable    = true
}

