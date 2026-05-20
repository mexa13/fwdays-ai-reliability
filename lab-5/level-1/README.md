# Level-1 — Beginner: Agent Sandbox + Phoenix tracing tutorial

You will:

1. Install the **Agent Sandbox** controller (and the **extensions** bundle that adds `SandboxTemplate`, `SandboxClaim`, `SandboxWarmPool`) into the `abox` cluster.
2. Reproduce the upstream **[network-policies use case](https://agent-sandbox.sigs.k8s.io/docs/use-cases/examples/network-policies/)** — spin up a `Sandbox`, then lock it down with a deny-by-default NetworkPolicy plus a DNS-only egress carve-out, and verify that the sandboxed pod *cannot* reach the public internet.
3. Run the **[Phoenix LangChain tracing Colab](https://colab.research.google.com/github/Arize-ai/phoenix/blob/main/tutorials/tracing/langchain_tracing_tutorial.ipynb)** to see what OpenTelemetry traces of an LLM application look like — this builds the mental model you'll need for level-2.

> **Note on `AgenticSandbox`.** The upstream network-policies tutorial uses an `AgenticSandbox` composite — that kind comes from a KRO `ResourceGraphDefinition` shipped in the upstream `dev/` tooling, *not* from the release `extensions.yaml` (verified against v0.4.6). To keep the lab portable we use the lower-level `Sandbox` CRD directly. The NetworkPolicies that this example is really about apply identically either way.

## Prerequisites

- `kind-abox` cluster from lab-1 / lab-2 (`make l2-run` or any of the other variants).
- `kubectl`, `curl`, `jq` on your PATH.
- (For step 3) a free Google account to open the Colab; no API key strictly required if you use the OpenAI-mocked variant in the notebook.

## Step 1 — Install the controller

```bash
cd lab-5/level-1

# One-time per cluster. Resolves the latest release tag and applies:
#   - manifest.yaml      (core: Sandbox CRD + controller + RBAC)
#   - extensions.yaml    (SandboxTemplate / SandboxClaim / SandboxWarmPool + ext controller)
make install-controller
make install-extensions

# Helpful for level-3 — the SDK talks to this proxy:
make install-router
make install-template            # installs python-sandbox-template into ns/default
```

Verify:

```bash
kubectl --context kind-abox -n agent-sandbox-system get pods
kubectl --context kind-abox get crd | grep agents.x-k8s.io
```

Expected: the `agent-sandbox-controller` pod is `Running` and you see four CRDs — `sandboxes.agents.x-k8s.io`, `sandboxtemplates.extensions.agents.x-k8s.io`, `sandboxclaims.extensions.agents.x-k8s.io`, `sandboxwarmpools.extensions.agents.x-k8s.io`.

## Step 2 — Apply the NetworkPolicy example

```bash
make deploy-example
make verify
```

`manifests/network-policy-example.yaml` creates:

| Resource | Purpose |
|---|---|
| `Namespace/a5-sandbox` | Workspace for the sandboxed pod |
| `Sandbox/demo` (`nicolaka/netshoot` + `sleep infinity`) | The actual sandbox; the controller fans this into a Pod |
| `NetworkPolicy/deny-all` | Drops everything ingress + egress |
| `NetworkPolicy/allow-dns` | Permits UDP/TCP 53 to `kube-system/kube-dns` only |

Confirm the egress is actually locked down:

```bash
SBOX=$(kubectl --context kind-abox -n a5-sandbox get pod -o jsonpath='{.items[0].metadata.name}')

# DNS works (allow-dns carve-out)
kubectl --context kind-abox -n a5-sandbox exec "$SBOX" -- nslookup kubernetes.default

# Public internet does NOT (deny-all still applies)
kubectl --context kind-abox -n a5-sandbox exec "$SBOX" -- \
  curl -sS --max-time 5 https://example.com || echo "✓ blocked as expected"
```

The netshoot image bundles `curl`, `nslookup`, `dig`, `ping` — handy for poking at NP behaviour.

> **Note — CNI requirements.** kind's default kindnet CNI honors `NetworkPolicy` on recent kind releases (≥ v0.20). If your cluster uses a CNI without NP enforcement (e.g. flannel without the policy plugin), the `deny-all` will be silently ignored — you'll see the curl succeed. Switch the cluster to a policy-aware CNI (Calico, Cilium) or interpret this as a "deploys but does not enforce" outcome.

## Step 3 — Phoenix tracing tutorial (Colab)

Open the upstream notebook:
**https://colab.research.google.com/github/Arize-ai/phoenix/blob/main/tutorials/tracing/langchain_tracing_tutorial.ipynb**

Run all cells top-to-bottom. The notebook will:

1. `pip install arize-phoenix langchain langchain-openai openinference-instrumentation-langchain`
2. Start an **embedded Phoenix server** inside Colab (`px.launch_app()`) — note the local URL it prints.
3. Build a small LangChain RAG chain, instrument it with `LangChainInstrumentor().instrument(tracer_provider=...)`, run a handful of queries.
4. Open the Phoenix UI and inspect the resulting traces — note the per-call latency, token counts, prompt/response payloads, and the span tree (`Chain` → `Retriever` → `LLM`).

What to take away before moving to level-2:

- **`openinference-instrumentation-*`** is the OpenAI-/Anthropic-/LangChain-/MCP-specific auto-instrumentation that turns library internals into OTel spans without you writing any wrapper code.
- **`phoenix.otel.register()`** wires the tracer provider into whichever Phoenix server you point it at — local in Colab, in-cluster in level-2.
- Phoenix is **just an OTLP backend with an LLM-aware UI**. Anything that exports OTLP works.

## Teardown

```bash
make teardown            # removes the example + controller + extensions
```

Skip `teardown-controller` if you're moving straight to level-2 — Phoenix doesn't need the controller, but level-3 reuses it.

## Verification table

| Step | Command | Expect |
|---|---|---|
| Controller up | `kubectl -n agent-sandbox-system get pods` | `agent-sandbox-controller-*  Running` |
| CRDs registered | `kubectl get crd \| grep agents.x-k8s.io` | four rows (`sandboxes`, `sandboxtemplates`, `sandboxclaims`, `sandboxwarmpools`) |
| Example healthy | `kubectl -n a5-sandbox get sandboxes` | `demo` exists; `kubectl -n a5-sandbox get pods` shows it `Running` |
| Deny works | `curl https://example.com` from inside the sandbox | timeout / connection refused |
| Allow-DNS works | `nslookup kubernetes.default` from inside the sandbox | resolves |

## Gotchas

- **`AgenticSandbox` is not in the release manifest.** In v0.4.x the higher-level composite is provided via a KRO `ResourceGraphDefinition` that lives in the upstream `dev/` tooling — not in `extensions.yaml`. We use the lower-level `Sandbox` directly to avoid pulling KRO into the lab. If you want the wrapper experience, follow the upstream install-kro script and apply their `rgd.yaml` on top of this lab.
- **NetworkPolicy enforcement is CNI-dependent.** kindnet enforces it on recent kind builds; some older CI setups ship without enforcement. Test the deny path before trusting it in your demo.
- **Template + router are not used in this level.** They're installed here so level-3's SDK demo can reuse them — feel free to skip those two targets if you're not running level-3.
- **`install-template` substitutes two variables.** Upstream `python-sandbox-template.yaml` is parameterised with `${SANDBOX_NAMESPACE}` and `${SANDBOX_TEMPLATE_NAME}`. The Makefile substitutes both at apply time; override with `make install-template SANDBOX_NAMESPACE=foo SANDBOX_TEMPLATE_NAME=bar`.
