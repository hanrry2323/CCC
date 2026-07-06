#!/usr/bin/env python3
"""ccc-dispatch.py — CCC v1.0 task dispatcher.

P0-2 of v1.0 automation plan.

Reads .ccc/plans/<task>.plan.md + .ccc/phases/<task>.phases.json,
infers required_capabilities, queries cluster-bus for active nodes,
outputs TRIPLE for HUMAN review:

  [dispatcher] plan=<task>
  [dispatcher] needed_capability=<L1|L2|L3 tag>
  [dispatcher] candidates:
    - <node_id> @ <host:port>, capabilities=[...], load=<n>
  [dispatcher] recommendation: <node_id> (capabilities match + load OK)
  [dispatcher] model_tier: <flash|sonnet|opus|max>
  [dispatcher] est_cost_seconds: <int>
  [dispatcher] VERDICT: ready-for-human-review (NOT auto-dispatch)

Then waits for stdin 'yes' before dispatching. Hard-fail otherwise.

Borrowed from:
  - clawmed-ai capability match (LESSON: it was commented out in v3.1)
  - agentmesh 6 projects consensus: TCP service registration + capability
  - red line 18: capability match DEFAULT (must NOT be optional)

SAFETY: this script does NOT auto-dispatch. Human must approve.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional


# --- Config ------------------------------------------------------------
DEFAULT_CLUSTER_BUS_URL = "http://127.0.0.1:9100"
DEFAULT_MODEL_TIER = "sonnet"  # CCC Executor default from roadmap §v1.0 #3

# --- Capability inference -----------------------------------------------
# Heuristic: extract capability tag from plan.md content.
# If plan contains explicit 'needs:' or 'requires:' markers, use those.
# Otherwise default to [claude-p, shell, git] for any coding task.
DEFAULT_NEEDED = ["claude-p", "shell"]


def infer_needed_capabilities(plan_path: Path) -> list[str]:
    """Extract capability requirements from plan.md.

    Recognized markers (case-insensitive):
      - 'capability: foo, bar' or 'needs: foo, bar' or 'requires: foo'
      - 'shell' / 'git' / 'python' keywords
    Falls back to DEFAULT_NEEDED.
    """
    if not plan_path.exists():
        return DEFAULT_NEEDED

    text = plan_path.read_text(errors="ignore")
    found = set()

    # Explicit markers
    for line in text.split("\n"):
        m = re.match(r"^\s*(?:needs?|required?\s*capabilit(?:y|ies)|capabilities?)\s*[:：]\s*(.+)$",
                      line, re.IGNORECASE)
        if m:
            for tok in re.split(r"[,\s]+", m.group(1).strip()):
                tok = tok.strip()
                if tok:
                    found.add(tok)

    # Keyword sniff (any of these words in the plan text)
    keywords = {
        "shell": "shell",
        "python": "python",
        "git": "git",
        "claude-p": "claude-p",
        "ollama": "ollama",
        "browser": "browser",
        "gpu": "gpu",
        "ssh": "ssh",
    }
    lower = text.lower()
    for kw, tag in keywords.items():
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            found.add(tag)

    return sorted(found) if found else DEFAULT_NEEDED


# --- Cluster-bus client ------------------------------------------------
def fetch_active_nodes(bus_url: str, timeout: float = 3.0) -> list[dict]:
    """GET /api/node/list from cluster-bus. Returns [] on unreachable."""
    url = f"{bus_url.rstrip('/')}/api/node/list"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data.get("nodes", [])
    except Exception as e:
        print(f"[dispatcher] cluster-bus unreachable at {url}: {e}", file=sys.stderr)
        return []


# --- Capability matching + scoring -------------------------------------
def match_capability(needed: list[str], node_caps: list[str], load: float) -> dict:
    """Score how well a node satisfies capability requirements.

    Strategy (v1.0 PoC): any-capability-overlap
      - matched count matters; perfect match preferred
      - 0 matches => not eligible
      - some matches (even 1) => eligible, weighted by coverage
      - load penalty applied

    This is intentionally LENIENT for v1.0 PoC. Future (red line 18)
    will add strict-required anchor via [REQUIRES]...[/REQUIRES] markers.
    """
    matched = sum(1 for c in needed if c in node_caps)
    if matched == 0 and needed:
        return {"matched": 0, "score": -1.0, "eligible": False}
    base = matched / len(needed) if needed else 1.0
    load_penalty = load / 200.0  # load 0..100 -> 0..0.5 penalty
    return {
        "matched": matched,
        "score": round(base - load_penalty, 3),
        "eligible": True,
    }


def select_node(needed: list[str], nodes: list[dict]) -> Optional[dict]:
    candidates = []
    for n in nodes:
        sc = match_capability(needed, n.get("capabilities", []), n.get("load", 0.0))
        candidates.append({**n, "match": sc})
    eligible = [c for c in candidates if c["match"]["eligible"]]
    if not eligible:
        return None
    eligible.sort(key=lambda c: c["match"]["score"], reverse=True)
    return eligible[0]


# --- Model tier inference ---------------------------------------------
def infer_model_tier(plan_path: Path) -> str:
    """Heuristic: plan length + criticality -> model tier.
    Mapping (tunable):
      - mentions 'opus' or 'max reasoning' => max
      - mentions 'critical' / 'security' => opus
      - else: sonnet (CCC default executor)
      - explicit 'flash' / 'minimax' => flash
    """
    if not plan_path.exists():
        return DEFAULT_MODEL_TIER
    text = plan_path.read_text(errors="ignore").lower()
    if "opus" in text or "security" in text or "critical" in text:
        return "opus"
    if "flash" in text or "minimax" in text or "trivial" in text:
        return "flash"
    return DEFAULT_MODEL_TIER


# --- Cost estimation ---------------------------------------------------
def estimate_cost_seconds(plan_path: Path, model_tier: str) -> int:
    """Heuristic cost model (rough): plan_line_count × tier_multiplier.

    Multipliers based on clawmed task_queue.json 4-task failure data (95% fail ≈ 2hr each).
    """
    if not plan_path.exists():
        return 600
    lines = sum(1 for _ in plan_path.open())
    multiplier = {"flash": 5, "sonnet": 15, "opus": 30, "max": 60}[model_tier]
    return min(lines * multiplier, 7200)


# --- Main dispatch -----------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True, help="path to plan.md")
    p.add_argument("--workspace", required=True, help="path to <workspace>/.ccc/")
    p.add_argument("--bus-url", default=DEFAULT_CLUSTER_BUS_URL)
    p.add_argument("--yes", action="store_true", help="auto-confirm dispatch (still requires explicit 'yes' stdin)")
    args = p.parse_args(argv)

    plan_path = Path(args.plan)
    workspace = Path(args.workspace)

    needed = infer_needed_capabilities(plan_path)
    model_tier = infer_model_tier(plan_path)
    est_cost = estimate_cost_seconds(plan_path, model_tier)
    nodes = fetch_active_nodes(args.bus_url)

    print("[dispatcher] plan=" + plan_path.name)
    print(f"[dispatcher] needed_capability={','.join(needed)}")
    if not nodes:
        print("[dispatcher] candidates: NONE (cluster-bus unreachable or no active nodes)")
        print("[dispatcher] recommendation: ABORT — cluster-bus must be reachable")
        print("[dispatcher] VERDICT: ABORT")
        return 2  # distinct exit code for ABORT

    print("[dispatcher] candidates:")
    for n in nodes:
        print(f"  - {n['node_id']} @ {n['host']}:{n['port']}, "
              f"capabilities={n.get('capabilities',[])}, load={n.get('load',0)}")

    picked = select_node(needed, nodes)
    if not picked:
        print("[dispatcher] recommendation: NO_NODE_HAS_REQUIRED_CAPABILITY")
        print(f"[dispatcher] needed={needed}")
        print("[dispatcher] registered capabilities:")
        all_caps = set()
        for n in nodes:
            all_caps.update(n.get("capabilities", []))
        print(f"[dispatcher]   {sorted(all_caps)}")
        print("[dispatcher] VERDICT: ABORT")
        return 3  # no eligible node

    # Triple output
    print(f"[dispatcher] recommendation: {picked['node_id']} "
          f"(score={picked['match']['score']})")
    print(f"[dispatcher] model_tier: {model_tier}")
    print(f"[dispatcher] est_cost_seconds: {est_cost}")
    print(f"[dispatcher] target: {picked['host']}:{picked['port']}")
    print("[dispatcher] VERDICT: ready-for-human-review (NOT auto-dispatch)")

    # Hard-gate: require explicit 'yes' from stdin
    if not args.yes:
        print("[dispatcher] AWAITING human confirmation: type 'yes' to dispatch")
        try:
            answer = input().strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print(f"[dispatcher] ABORT — confirmation received: {answer!r}")
            return 4

    # If confirmed: emit a dispatch artifact (dry-run only for v1.0 PoC)
    dispatch_dir = workspace / "dispatches"
    dispatch_dir.mkdir(exist_ok=True)
    artifact = dispatch_dir / f"dispatch-{plan_path.stem}.json"
    artifact.write_text(json.dumps({
        "plan": str(plan_path),
        "picked_node": picked["node_id"],
        "target": f"{picked['host']}:{picked['port']}",
        "needed_capability": needed,
        "model_tier": model_tier,
        "est_cost_seconds": est_cost,
        "dispatched_at": 0,  # PoC: not actually firing
        "note": "v1.0 PoC — not actually dispatched. M1 still dispatches manually.",
    }, indent=2))
    print(f"[dispatcher] artifact: {artifact}")
    print("[dispatcher] done (PoC mode — no actual claude -p fired)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
