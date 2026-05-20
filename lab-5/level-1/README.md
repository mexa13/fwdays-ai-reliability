# Level-1 — Beginner: Agent Sandbox + Phoenix tracing tutorial

You will:

1. Install the **Agent Sandbox** controller (and the optional **extensions** that provide the higher-level `AgenticSandbox` wrapper) into the `abox` cluster.
2. Reproduce the upstream **[network-policies use case](https://agent-sandbox.sigs.k8s.io/docs/use-cases/examples/network-policies/)**: spin up an `AgenticSandbox`, then lock it down with a deny-by-default NetworkPolicy plus a DNS-only egress carve-out — verify that the sandboxed pod *cannot* reach the public internet.
3. Run the **[Phoenix LangChain tracing Colab](https://colab.research.google.com/github/Arize-ai/phoenix/blob/main/tutorials/tracing/langchain_tracing_tutorial.ipynb)** to see what OpenTelemetry traces of an LLM application look like — this builds the mental model you'll need for level-2.

## Prerequisites

- `kind-abox` cluster from lab-1 / lab-2 (`make l2-run` or any of the other variants).
- `kubectl`, `curl`, `jq` on your PATH.
- (For step 3) a free Google account to open the Colab; no API key strictly required if you use the OpenAI-mocked variant in the notebook.

## Step 1 — Install the controller

```bash
cd lab-5/level-1

# One-time per cluster. Resolves the latest release tag and applies:
#   - manifest.yaml      (Sandbox + SandboxTemplate CRDs + controller)
#   - extensions.yaml    (KRO-backed AgenticSandbox ResourceGraphDefinition)
make install-controller
make install-extensions

# Helpful for level-3 — the SDK talks to this proxy:
make install-router
make install-template
```

Verify:

```bash
kubectl --context kind-abox -n agent-sandbox-system get pods
kubectl --context kind-abox get crd | grep agents.x-k8s.io
```

Expected: the `agent-sandbox-controller-manager` pod is `Running` and you see `sandboxes.agents.x-k8s.io`, `sandboxtemplates.agents.x-k8s.io`, and the AgenticSandbox CRD registered.

## Step 2 — Apply the NetworkPolicy example

```bash
make deploy-example
make verify
```

`manifests/network-policy-example.yaml` creates:

| Resource | Purpose |
|---|---|
| `Namespace/a5-sandbox` | Workspace for the sandboxed pod |
| `AgenticSandbox/demo` (nginx + svc:80) | The high-level wrapper — controller expands it into a `Sandbox` + `Service` |
| `NetworkPolicy/deny-all` | Drops everything ingress + egress |
| `NetworkPolicy/allow-dns` | Permits UDP/TCP 53 to `kube-system/kube-dns` only |

Confirm the egress is actually locked down:

```bash
SBOX=$(kubectl --context kind-abox -n a5-sandbox get pod \
  -l agents.x-k8s.io/sandbox=demo -o jsonpath='{.items[0].metadata.name}')

# DNS works (allow-dns carve-out)
kubectl --context kind-abox -n a5-sandbox exec "$SBOX" -- nslookup kubernetes.default

# Public internet does NOT (deny-all still applies)
kubectl --context kind-abox -n a5-sandbox exec "$SBOX" -- \
  curl -sS --max-time 5 https://example.com || echo "✓ blocked as expected"
```

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
| Controller up | `kubectl -n agent-sandbox-system get pods` | `agent-sandbox-controller-manager-*  Running` |
| CRDs registered | `kubectl get crd \| grep agents.x-k8s.io` | three rows (`sandboxes`, `sandboxtemplates`, `agenticsandboxes`) |
| Example healthy | `kubectl -n a5-sandbox get agenticsandboxes` | `demo` exists; `kubectl get svc` shows `demo:80` |
| Deny works | `curl https://example.com` from inside the sandbox | timeout / connection refused |
| Allow-DNS works | `nslookup kubernetes.default` from inside the sandbox | resolves |

## Gotchas

- **`AgenticSandbox` requires KRO.** It's installed as part of `extensions.yaml`. If the wrapper stays in `Pending`, check the KRO controller pod.
- **NetworkPolicy enforcement is CNI-dependent.** kindnet enforces it on recent kind builds; some older CI setups ship without enforcement. Test the deny path before trusting it in your demo.
- **Template + router are not used in this level.** They're installed here so level-3's SDK demo can reuse them — feel free to skip those two targets if you're not running level-3.
