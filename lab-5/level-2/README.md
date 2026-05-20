# Level-2 — Experienced: Phoenix in abox + Sandbox metrics + MCP tracing

You will:

1. Deploy **Arize Phoenix** into `abox` via the official OCI Helm chart and reach its UI at `http://localhost:6006`.
2. Deploy an **OpenTelemetry Collector** that (a) forwards OTLP traces to Phoenix and (b) Prometheus-scrapes the OpenTelemetry-derived metrics that the **Agent Sandbox runtimes** publish (see the upstream [metrics doc](https://agent-sandbox.sigs.k8s.io/docs/sandbox/metrics/)).
3. Build a small **MCP server** instrumented with `openinference-instrumentation-mcp` + `phoenix.otel.register()` and watch its tool calls light up in the Phoenix UI.

## Architecture

```
                                            ┌──────────────────────────────────┐
   reliability-mcp-traced ──OTLP HTTP:6006──▶│ Phoenix    UI :6006              │
   (FastMCP + openinference)                 │            OTLP gRPC :4317       │
                                             └──────────────────────────────────┘
                                                          ▲
                                                          │ OTLP gRPC
   Agent Sandbox runtimes ──Prom annotations──▶ otel-collector (in ns/phoenix)
   (port 9464 by convention)
```

Phoenix accepts OTLP directly, so for tracing only you don't strictly need the Collector. The Collector earns its keep here for **metrics**: it Prom-scrapes Sandbox runtime pods (annotated `prometheus.io/scrape: "true"`) and re-exposes them on `:8889` for inspection.

## Prerequisites

- `kind-abox` cluster from lab-1 / lab-2.
- `kubectl`, `helm`, `docker`, `kind` on your PATH.
- (Recommended) level-1 deployed, so the Agent Sandbox runtimes actually exist for the Collector to scrape.

## Step 1 — Deploy Phoenix

```bash
cd lab-5/level-2
make deploy-phoenix
```

The chart `oci://registry-1.docker.io/arizephoenix/phoenix-helm` is installed into `ns/phoenix` with values in [`manifests/phoenix-values.yaml`](./manifests/phoenix-values.yaml). Defaults:

- SQLite store (no Postgres subchart).
- ClusterIP Service `phoenix` on `6006/tcp` (UI + OTLP HTTP) and `4317/tcp` (OTLP gRPC).
- 5 Gi PVC for span storage.

Open the UI:

```bash
make port-forward-phoenix       # blocks; ctrl-c to stop
# → http://localhost:6006
```

## Step 2 — OTel Collector

```bash
make deploy-collector
```

[`manifests/otel-collector.yaml`](./manifests/otel-collector.yaml) deploys a single `otel-collector` pod with:

- **Receivers** — `otlp` (gRPC :4317, HTTP :4318), `prometheus` (Kubernetes service discovery, keeps only pods with `prometheus.io/scrape=true`).
- **Exporters** — `otlp/phoenix` (sends spans to Phoenix on 4317), `prometheus` (re-exports metrics on :8889).
- **Service** — `otel-collector` in `ns/phoenix`, ports 4317/4318/8889.

Once it's running, agents can point either at the Collector (`otel-collector.phoenix:4317`) for centralised pipelines, or directly at Phoenix.

## Step 3 — Instrumented MCP server

The server lives in [`mcp-traced/server.py`](./mcp-traced/server.py). Highlights:

```python
from phoenix.otel import register
tracer_provider = register(
    project_name="lab-5-mcp",
    endpoint="http://phoenix.phoenix.svc.cluster.local:6006",
    auto_instrument=True,
)
tracer = tracer_provider.get_tracer("reliability-mcp")

mcp = FastMCP("reliability-mcp")

@mcp.tool()
@tracer.tool(name="MCP.error_budget")
def error_budget(slo_percent: float, window_days: int = 30) -> dict: ...
```

- `register(auto_instrument=True)` activates **every installed openinference instrumentation** including `openinference-instrumentation-mcp`. The MCP layer wraps `FastMCP` so each JSON-RPC request becomes a span tree.
- `@tracer.tool(name="...")` adds an inner span per tool invocation, capturing arguments and return value as span attributes.

Build, load, deploy:

```bash
make deploy-mcp                 # build → kind load → kubectl apply
make test-trace                 # exec the pod, invoke both tools
```

Refresh Phoenix at `http://localhost:6006`. You should see project **`lab-5-mcp`** with two new traces (`MCP.error_budget`, `MCP.toy_incident_triage`) — each with the input args and return value visible on the span detail.

## One-shot

```bash
make deploy                     # Phoenix + Collector + MCP in order
make port-forward-phoenix       # in a second terminal
make test-trace
```

## Sandbox metrics — what to look for

The upstream [Sandbox metrics doc](https://agent-sandbox.sigs.k8s.io/docs/sandbox/metrics/) lists OpenTelemetry-SDK auto-instrumentation metrics that Sandbox runtimes expose when started via `opentelemetry-instrument` (e.g. `otel.sdk.span.started`, `http.client.duration`). To capture them:

1. In your Sandbox runtime image (e.g. the python-sandbox-template), set:
   ```
   OTEL_TRACES_EXPORTER=otlp
   OTEL_METRICS_EXPORTER=prometheus
   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.phoenix:4317
   ```
2. Add pod annotations `prometheus.io/scrape: "true"` and `prometheus.io/port: "9464"` (the default prometheus exporter port).
3. Curl the Collector's re-exporter to confirm the metrics arrived:
   ```bash
   kubectl --context kind-abox -n phoenix port-forward svc/otel-collector 8889:8889
   curl -s http://localhost:8889/metrics | grep -E 'otel_sdk|http_client_duration'
   ```

The traces from the same Sandbox runtimes will land in Phoenix automatically because the Collector forwards OTLP there.

## Local dev (no cluster)

```bash
make install-local
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006 make run-local
```

Run a separate Phoenix locally via `pip install arize-phoenix && phoenix serve` if you don't want the kind round-trip.

## Verification table

| Step | Command | Expect |
|---|---|---|
| Phoenix UI | `curl http://localhost:6006/healthz` (with port-forward) | `200 OK` |
| Phoenix OTLP gRPC | `nc -zv localhost 4317` | succeeded |
| Collector | `kubectl -n phoenix get pods` | `otel-collector-*` `Running` |
| MCP server | `kubectl -n a5-observe get pods` | `reliability-mcp-traced-*` `Running` |
| Tool span emitted | `make test-trace`, then refresh Phoenix UI | new spans under project `lab-5-mcp` |
| Sandbox metrics scraped | `curl localhost:8889/metrics \| grep otel_sdk` | non-zero counters once a Sandbox runtime is running |

## Gotchas

- **Phoenix Helm chart version.** `PHOENIX_VER` defaults to `12.5.0`. Bump to the latest from `oci://registry-1.docker.io/arizephoenix/phoenix-helm` if the chart API has moved on; the values file uses the stable keys (`server.*`, `service.*`, `persistence.*`, `auth.*`).
- **PVC stays around after teardown.** `helm uninstall` doesn't delete PVCs by default. Run `kubectl -n phoenix delete pvc --all` if you want a clean slate.
- **`phoenix.otel.register(endpoint=...)`** auto-selects HTTP vs gRPC by port. Port 6006 → HTTP OTLP at `/v1/traces`; port 4317 → gRPC. Both work here.
- **Annotations vs ServiceMonitor.** The Collector uses Prometheus pod-annotation discovery to keep things light — no Prometheus Operator required. If you already run kube-prometheus-stack, swap to ServiceMonitor.
