# Rollback Playbook

## When to rollback

- Service health check fails repeatedly after deployment.
- Critical alert firing for >5 minutes.
- Error budget burn alert is triggered.

## Rollback steps

1. Freeze further deployments.
2. Roll back the affected Helm release:
   - `helm history <release>`
   - `helm rollback <release> <revision>`
3. Verify `/health` and `/metrics` endpoints.
4. Run smoke checks from `scripts/smoke-contract.sh`.
5. Confirm alert recovery and close incident.

## Post-incident

- Record incident timeline.
- Add regression test or contract test to prevent recurrence.
