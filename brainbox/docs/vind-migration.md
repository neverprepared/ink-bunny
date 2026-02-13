# vind Migration Notes

## Decision

Replace direct Docker commands with vCluster in Docker (vind) as the runtime layer. **Thin wrapper approach** — keep the single-container-per-session model, use vind for create/pause/resume/delete instead of docker start/stop.

Status: **deferred** — revisiting later.

## Prerequisites

- `brew install loft-sh/tap/vcluster`
- `vcluster use driver docker`
- Docker running

## References

- https://github.com/loft-sh/vind
- https://www.vcluster.com/docs/vcluster/deploy/control-plane/docker-container/basics

## Key benefits over raw Docker

- Sleep/wake (pause/resume) with state preservation
- Kubernetes Secrets instead of manual .env injection
- Liveness/readiness probes instead of HEALTHCHECK
- Declarative YAML manifests
- Path toward Phase 2/3 architecture (SPIRE, OPA/Kyverno, Envoy)

## Migration scope (thin wrapper)

Replace in `lib/lifecycle.js`:
- `docker create` → `vcluster create` + `kubectl apply` (Pod)
- `docker start` → `vcluster resume` or Pod already running
- `docker stop` → `vcluster pause`
- `docker rm` → `vcluster delete`
- Port exposure → `type: LoadBalancer` Service
- Volumes → `experimental.docker.volumes` + `hostPath` in Pod spec
