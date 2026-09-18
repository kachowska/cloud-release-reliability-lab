provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

resource "kubernetes_namespace_v1" "release" {
  metadata {
    name = var.namespace

    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "lab.release/environment"      = var.environment
    }
  }
}

module "release_service" {
  source = "./modules/release-service"

  namespace         = kubernetes_namespace_v1.release.metadata[0].name
  name              = var.name
  image             = var.image
  image_pull_policy = var.image_pull_policy
  replicas          = var.replicas
  release_version   = var.release_version
  commit_sha        = var.commit_sha
  environment       = var.environment
  force_not_ready   = var.force_not_ready
}

