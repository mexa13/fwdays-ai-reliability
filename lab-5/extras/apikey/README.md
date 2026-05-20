# Extras: agentgateway API key authentication

Per the upstream [API key tutorial](https://agentgateway.dev/docs/kubernetes/latest/security/apikey/). Adds two resources:

- a `Secret` typed `extauth.solo.io/apikey` holding the static key,
- an `AgentgatewayPolicy` in **Strict** mode bound to the `agentgateway-proxy` Gateway — requests without the key are rejected.

```bash
make apply              # apply both resources
make test               # 401 without key, 200 with key
make teardown
```

`mode: Strict` is the lockdown setting. Switch to `mode: Optional` (file already shows the alternate selector form in lab-5 root README references) if you want both authenticated and unauthenticated traffic but want the gateway to *tag* authenticated requests.

Production checklist:

- Rotate the key in `apikey.yaml` (or wire to a real secret manager via the Helm chart).
- Move to a `secretSelector` with labels so multiple keys can be added without editing the policy.
- Combine with the guardrails extra so authenticated traffic is still content-checked before the LLM call.
