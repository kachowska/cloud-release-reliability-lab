variable "namespace" {
  type = string
}

variable "name" {
  type = string
}

variable "image" {
  type = string
}

variable "image_pull_policy" {
  type = string
}

variable "replicas" {
  type = number
}

variable "release_version" {
  type = string
}

variable "commit_sha" {
  type = string
}

variable "environment" {
  type = string
}

variable "force_not_ready" {
  type = bool
}

