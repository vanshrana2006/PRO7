# Kubernetes manifests

Scaffolding for a production cluster deployment. **These are correct,
reviewed YAML, but not applied against a live cluster from this
environment** (no cluster access here) -- treat this the same way as the
rest of the network/infra layer in `docs/GAP_ANALYSIS.md`: written to
production standard, verify on your own cluster before relying on it.

## Apply order

```bash
kubectl apply -f 00-namespace-config.yaml
kubectl apply -f 01-backend.yaml
kubectl apply -f 02-frontend.yaml
kubectl apply -f 03-frontend-hpa.yaml
```

## Before you apply

1. **Build and push images** to a registry the cluster can pull from, and
   update the `image:` fields in `01-backend.yaml`/`02-frontend.yaml`.
2. **Set real secrets** in `00-namespace-config.yaml`'s `Secret`, or better,
   manage them via your cluster's secret tooling (Sealed Secrets, External
   Secrets Operator, etc) instead of committing them in plain YAML.
3. **Swap SQLite for Postgres** before scaling the backend past 1 replica
   -- see the comment in `01-backend.yaml`. `DATABASE_URL` is the only
   change needed; the application code is already dialect-agnostic.
4. **Point DNS + TLS** at your ingress controller and update the `host`
   values in `02-frontend.yaml`'s Ingress. Add a cert-manager `Certificate`
   resource (not included here) for HTTPS.
5. **Install an ingress controller** (e.g. `ingress-nginx`) if the cluster
   doesn't already have one.

## Not included, and why

- **cert-manager / TLS resources** -- depends on your DNS provider and
  ACME setup, which isn't something to guess at generically.
- **Postgres/Redis StatefulSets** -- once you've decided on managed vs.
  self-hosted, that's a small addition following the same pattern as
  `01-backend.yaml`; a managed database (RDS, Cloud SQL, etc) is generally
  the better choice for production and needs no manifest here at all.
- **NetworkPolicies** -- worth adding once your cluster's namespace
  topology is settled; a generic one here would either be too permissive
  to be meaningful or too specific to your setup to be correct.
