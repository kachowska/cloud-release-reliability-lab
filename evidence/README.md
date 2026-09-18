# Generated evidence

Run `scripts/validate.sh` to create `local-validation.json`,
`local-validation.md`, and `pytest.xml` from real commands. A Kubernetes run of
`scripts/failure-drill.sh` additionally creates `kubernetes-drill.json` and
`kubernetes-drill.md`.

Generated files are ignored by Git because results belong to a specific runtime.
They must never be replaced with hand-authored success claims.

