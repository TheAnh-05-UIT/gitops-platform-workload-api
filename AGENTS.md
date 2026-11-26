# Workload API repository

When the Platform checkout is available, read its [shared workspace policy](../gitops-platform/docs/WORKSPACE_POLICY.md) and manually open the relevant `../gitops-platform/.agents/skills/<name>/SKILL.md`. In a standalone clone, follow the local rules below and coordinate downstream changes with the Config and Platform owners.

- Keep `GET /` returning the workload identity and version, and `GET /healthz` returning the readiness response. Preserve Gunicorn entry point through `workload_api.app:app` and the container's non-root UID and port `8080`.
- Run a Flask test-client smoke check for both routes and, when Docker is available, build and locally probe the image using the commands and assertions in `.github/workflows/ci.yml`. Add regression tests for changed behavior.
- Preserve the GHCR repository and full commit-SHA tag contract. Validate before publishing. Treat publication and config promotion as distinct steps. Update the config owner before changing image references, ports, readiness semantics or resource needs.
- Preserve existing changes, avoid destructive Git operations and keep credentials out of source and logs. Require explicit authorization to commit, push, open, approve or merge a remote PR, publish an image, or deploy.
