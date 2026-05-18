# Lab-3: MCP Sampling, Elicitation & Apps on abox

**Platform:** [abox](https://github.com/den-vasyliev/abox) — Kubernetes AI infrastructure sandbox
**Stack:** kmcp · kagent · FastMCP 3.x · agentgateway · google-agents-cli · MCP Inspector 0.21.1

This lab extends [lab-2/level-3](../lab-2/level-3/) with three new MCP capabilities and a second agent dev/test flow built on `google-agents-cli`.

---

## Tracks

| Level | Track | Deliverable |
|---|---|---|
| [level-1](./level-1/) | **Beginners** | Custom KMCP server deployed to abox, agent built with `google-agents-cli`, exercised via MCP Inspector + agents-cli playground |
| [level-2](./level-2/) | **Experienced** | level-1 + **MCP Apps** case: incident dashboard rendered as an embedded UI widget |
| [level-3](./level-3/) | **Max** | level-2 + **MCP Sampling / Elicitation** case: triage flow that elicits user input and uses the host's LLM to draft a stakeholder update |

Research deliverable: [`docs/research.md`](./docs/research.md) — technical & business cases for each capability.

---

## Prerequisites

abox cluster running (`kind-abox` context — see [lab-2 README](../lab-2/README.md)):

```bash
cd /path/to/abox && make run
kubectl --context kind-abox get pods -A | grep -E 'kagent|agentgateway|flux'
```

Required toolchain (installed on demand from each level's Makefile):

- Docker + `kind` (for `kind load docker-image` local dev)
- `kubectl` with `kind-abox` context
- Python 3.11+, `pip`, `venv`
- `npx` (Node.js 20+) — for `@modelcontextprotocol/inspector`
- `uvx` (or `pipx`) — for `google-agents-cli`
- `helm`, `flux` — only for the GitLessOps path (optional)

---

## Quick start

```bash
# Level 1 — beginners
cd lab-3/level-1
make deploy IMAGE=ghcr.io/<your-org>/reliability-mcp-v2 TAG=v0.1.0
make inspector            # opens MCP Inspector against the in-cluster server
make playground           # starts agents-cli playground against the same server

# Level 2 — MCP Apps
cd lab-3/level-2
make deploy IMAGE=ghcr.io/<your-org>/reliability-mcp-apps TAG=v0.1.0

# Level 3 — Sampling + Elicitation
cd lab-3/level-3
make deploy IMAGE=ghcr.io/<your-org>/reliability-mcp-sampling TAG=v0.1.0
```

Each `make deploy` builds, pushes (or `kind load`s), and applies the `MCPServer` + `Agent` CRDs to `kind-abox`.

---

## Repository layout

```
lab-3/
├── README.md                    # this file
├── Makefile                     # root entrypoint (l3l1-*, l3l2-*, l3l3-*)
├── docs/
│   └── research.md              # research deliverable
├── level-1/                     # beginners — KMCP + agents-cli + Inspector
│   ├── README.md
│   ├── Makefile
│   ├── mcp-server/              # FastMCP server (extended reliability toolset)
│   ├── manifests/               # MCPServer + RemoteMCPServer + Agent
│   └── agents-cli/              # agent spec for google-agents-cli playground
├── level-2/                     # experienced — MCP Apps
│   ├── README.md
│   ├── Makefile
│   ├── mcp-server/              # FastMCP server with @mcp.tool(app=True)
│   └── manifests/
└── level-3/                     # max — Sampling + Elicitation
    ├── README.md
    ├── Makefile
    ├── mcp-server/              # FastMCP server with ctx.sample / ctx.elicit
    └── manifests/
```

---

## How each level builds on the last

```
level-1 ─┐
         ├─► reliability tooling foundation, headless deploy via kmcp
level-2 ─┘
         ├─► same server + Apps UI surface (in-chat dashboards)
level-3 ─┘
         └─► same server + Sampling (server→host LLM) + Elicitation (server→user)
```

The Docker image is rebuilt at each level — different `IMAGE` names so you can run them side by side in `kagent`.

---

## Cleanup

```bash
make l3-down                     # tear down all three levels' resources from kind-abox
```
