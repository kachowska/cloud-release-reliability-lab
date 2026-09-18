# Azure target: configuration only

This directory maps the validated local design to a minimal Azure target: an Azure
Container Registry, an AKS cluster with managed identity, and an `AcrPull` role
assignment. It is included to make the migration decisions inspectable.

No Azure login, plan, apply, resource creation, workload deployment, or cost validation
has been performed as part of the local lab. `terraform validate` checks configuration
shape only; it does not prove that a subscription has quota, that a chosen Kubernetes
version is available, or that these defaults meet a production security review.

Before any real use, a platform owner should add a remote encrypted state backend with
locking, private networking, approved identity/RBAC, policy controls, monitoring,
backup/recovery requirements, and an explicit cost review. Never run `terraform apply`
from this directory without authorization for paid Azure resources.

