#!/usr/bin/env python3
"""
Bottleneck Instructor - Improved System for Proactive Text Instructions

When the user (Nir) is the bottleneck across the digital business effort (approvals, decisions, feedback, creative input), this generates and sends RICH, ACTIONABLE, LINKED instructions via OpenClaw (iMessage) using the max-scope/min-input/rapid-quality principle.

Goal tie-in: Every instruction advances the fully automated revenue business platform (traffic acquisition -> conversion funnels -> monetization via ads/affiliates/subs/leads/tools/direct sales from domain portfolio).

Usage (called from crons/agents/cycle):
  python3 bottleneck_instructor.py --detect --send
  python3 bottleneck_instructor.py --domain watershortcut.com --task "approve these revenue pitches" --link "https://nnlevy.github.io/portfolio-outreach-viewer/?domain=watershortcut.com" --revenue-impact "affiliate commissions + tool trials"

It detects from:
- promotion_state.json (pending_approvals)
- prompt_queue / LATEST (blocked items)
- missing snapshots/inventory from reports/state
- orchestration health
- user-defined bottlenecks in state/outreach/bottlenecks.json

Generates text like:
"Revenue Platform Bottleneck: watershortcut.com promotion.
Task: Review/approve these monetization drafts (affiliate for calculators + ad intros for utilities) at https://nnlevy.github.io/portfolio-outreach-viewer/ 
Revenue impact: This unlocks automated traffic->conversion->affiliate/subs revenue loop with minimal input.
Options (minimal input):
1. APPROVE watershortcut.com (I will mark + trigger next: content deploy + revenue pitch cron)
2. FEEDBACK: [domain-specific: ...] [general: ...] (I will update learnings.json + regenerate)
3. SKIP + reason (I will log + deprioritize)
Expected: Higher quality drafts next cycle via your learnings. Full context in PORTFOLIO_REVENUE_BUSINESS_MANIFESTO.md
Reply with number or structured text."

On processing reply (in agent context or via record): updates state/learnings, can trigger follow-on automation.

This is the improved system: not ad-hoc commands, but structured, revenue-tied, link-heavy, auto-learning instructions that require only your high-signal reply.

Integrates with promotion_cycle (for outreach), can be called from any cron/agent for general business (content, deploy, billing, ads, traffic).

Run via openclaw agentTurn or directly in scripts.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

WORKSPACE = Path("/Users/nirlevy/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "outreach"
PROMOTION_STATE = STATE_DIR / "promotion_state.json"
LEARNINGS = STATE_DIR / "learnings.json"
BOTTLENECKS = STATE_DIR / "bottlenecks.json"
LATEST_REPORT = WORKSPACE / "reports" / "portfolio_factory" / "LATEST.md"
MANIFESTO = WORKSPACE / "PORTFOLIO_REVENUE_BUSINESS_MANIFESTO.md"
VIEWER_URL = "https://nnlevy.github.io/portfolio-outreach-viewer/"

PHONE = "+14049844781"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(p: Path, default: Any = None) -> Any:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            pass
    return default or {}

def detect_bottlenecks() -> List[Dict[str, str]]:
    bottlenecks: List[Dict[str, str]] = []
    promo = load_json(PROMOTION_STATE, {})
    for p in promo.get("pending_approvals", []):
        if p.get("status") == "pending_approval":
            bottlenecks.append({
                "domain": p["domain"],
                "type": "promotion_approval",
                "description": f"Approve revenue/feedback drafts for {p['domain']}",
                "link": f"{VIEWER_URL}?domain={p['domain']}",
                "revenue_impact": "Advances validation -> monetization loop (affiliates, ads, tool trials) for domain revenue platform."
            })

    # From prompt queue / LATEST (simple parse)
    latest = load_json(WORKSPACE / "reports/portfolio_factory/latest.json", {})
    queue = latest.get("queue", {})
    if queue.get("warnings", 0) > 0 or queue.get("errors", 0) > 0:
        bottlenecks.append({
            "domain": "portfolio",
            "type": "orchestration_health",
            "description": "Review blocked items in prompt queue / LATEST (visualtos, contentasaservice, fleetrepair, healthwellnessjobs etc.)",
            "link": "https://nnlevy.github.io/portfolio-outreach-viewer/ or qmd://portfolio_factory/LATEST.md",
            "revenue_impact": "Unblocks revenue lanes (many domains in revenue pool) and factory automation for portfolio-wide revenue generation."
        })

    # Missing snapshots (from action queue in LATEST or dashboard)
    action_queue = latest.get("action_queue", [])
    if any("snapshot" in str(a).lower() for a in action_queue):
        bottlenecks.append({
            "domain": "portfolio",
            "type": "missing_snapshots",
            "description": "Restore missing source snapshots (cloudflare-inventory, pr_review_gate, leases, locks, repo_coherence)",
            "link": "qmd://portfolio_factory/LATEST.md or dashboard",
            "revenue_impact": "Foundation for all revenue automation (deploy, publish, billing, ads, traffic). Without snapshots, monetization experiments and deploys are blocked."
        })

    # User-defined
    user_b = load_json(BOTTLENECKS, {"items": []})
    for item in user_b.get("items", []):
        bottlenecks.append(item)

    return bottlenecks

def generate_instruction(b: Dict[str, str]) -> str:
    domain = b.get("domain", "portfolio")
    desc = b.get("description", "")
    link = b.get("link", VIEWER_URL)
    impact = b.get("revenue_impact", "Advances the fully automated revenue platform from domain portfolio.")
    manifesto_link = "https://nnlevy.github.io/portfolio-outreach-viewer/PORTFOLIO_REVENUE_BUSINESS_MANIFESTO.md (or local workspace/ )"

    # Generate short unique ID for this approval item to survive quote transcription and allow reliable lookup of which message/domain (per user feedback on quote-reply context loss)
    from datetime import datetime
    short_id = f"{domain.split('.')[0]}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    # Persist ID -> domain map for the agent to lookup when user replies with the ID
    map_path = STATE_DIR / "approval_map.json"
    amap = {}
    if map_path.exists():
        try:
            amap = json.loads(map_path.read_text())
        except:
            pass
    amap[short_id] = domain
    map_path.write_text(json.dumps(amap, indent=2))

    # Enforce explicit "Approve?" prefix when approval is required (per user feedback: quote-replies need clear context)
    is_approval = "approve" in desc.lower() or "approval" in b.get("type", "").lower() or "pending" in b.get("type", "").lower()
    prefix = "Approve? " if is_approval else ""

    text = f"""{prefix}[ID: {short_id}] Revenue Platform Bottleneck: {domain} — {desc}

Goal: Build fully automated business platform generating revenue from domain portfolio (max traffic->conversion->monetization via ads/affiliates/subs/leads/tools; min your input; rapid quality via learnings).

Task: {desc}
Link (review on phone Safari, use forms for feedback): {link}
Revenue impact: {impact}

Instructions (max-scope automation done; your min input needed):
- Read manifesto first if new: {manifesto_link}
- Review the linked drafts/viewer/state.
- To approve: Quote this entire message in your iMessage reply and start with "Approve? {short_id} YES" (or "Approve? {short_id} NO + reason" or "Approve? {short_id} FEEDBACK: [specific to {domain}: ...] [general across domains: ...]"). Or simply reply "Approve? {short_id} YES" (the ID lets the agent lookup the exact previous message and domain even if quote transcription is imperfect). The agent will use the ID or quoted context + your words to process exactly (mark the correct domain, log to learnings, trigger next automation for that domain).
- SKIP {domain} + reason   (I will log, deprioritize, surface in next audit)

This text was generated by bottleneck_instructor.py (integrated in promotion_cycle and callable from any cron/agent). Your reply with the ID will be parsed (agent loads approval_map.json to map ID to domain) to improve the system (domain-specific + general learnings feed generator for rapidly better outputs).

Full context + current state + priorities in manifesto + viewer. Principle applied: I did the max work (detection, generation with ID, links, auto-update) so you only provide high-signal input.

Reply now (quoting this message and starting with Approve? {short_id} ... or just the ID) to unblock and compound quality."""
    return text

def send_via_openclaw(text: str, target: str = PHONE) -> bool:
    try:
        # Use openclaw agent for delivery (as used in crons/previous sends)
        cmd = ["openclaw", "agent", "--to", target, "--message", text, "--deliver"]
        subprocess.run(cmd, check=True, timeout=60, capture_output=True)
        print("Sent via openclaw agent --deliver")
        return True
    except Exception as e:
        print(f"OpenClaw send failed: {e}. Falling back to direct message send...")
        try:
            cmd2 = ["openclaw", "message", "send", "--channel", "imessage", "--target", target, "--message", text]
            subprocess.run(cmd2, check=True, timeout=60, capture_output=True)
            print("Sent via openclaw message send")
            return True
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            print("MANUAL: Copy this text and send to your phone/iMessage thread:")
            print(text)
            return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detect", action="store_true", help="Detect current bottlenecks and generate instructions")
    parser.add_argument("--send", action="store_true", help="Send the generated instructions via OpenClaw text")
    parser.add_argument("--domain", help="Specific domain for custom instruction")
    parser.add_argument("--task", help="Custom task description")
    parser.add_argument("--link", help="Custom link (usually the viewer)")
    parser.add_argument("--revenue-impact", help="Custom revenue impact statement")
    parser.add_argument("--force-text", help="Force send this exact text (for testing)")
    args = parser.parse_args()

    if args.force_text:
        text = args.force_text
        if args.send:
            send_via_openclaw(text)
        else:
            print(text)
        return 0

    bottlenecks = []
    if args.domain and args.task:
        bottlenecks = [{
            "domain": args.domain,
            "type": "custom",
            "description": args.task,
            "link": args.link or VIEWER_URL,
            "revenue_impact": args.revenue_impact or "Advances automated revenue platform."
        }]
    elif args.detect:
        bottlenecks = detect_bottlenecks()

    if not bottlenecks:
        print("No bottlenecks detected (or provide --domain + --task).")
        return 0

    print(f"Detected {len(bottlenecks)} bottleneck(s).")
    for b in bottlenecks:
        text = generate_instruction(b)
        print("\n=== INSTRUCTION ===\n" + text + "\n===================\n")
        if args.send:
            send_via_openclaw(text)
            # Optionally mark or log that instruction was sent
            state = load_json(PROMOTION_STATE, {})
            # simple log
            sent_log = STATE_DIR / "sent_instructions.jsonl"
            with sent_log.open("a") as f:
                f.write(json.dumps({"ts": now_iso(), "bottleneck": b, "text_preview": text[:200]}) + "\n")

    # Update learnings or state if custom
    if args.domain:
        learns = load_json(LEARNINGS, {})
        # nothing auto; user reply will feed via record

    return 0

if __name__ == "__main__":
    sys.exit(main())
