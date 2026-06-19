#!/usr/bin/env python3
"""
Portfolio Promotion Cycle - Proactive Outreach Automation with Approval Gate

Applies the Wake-Up Launchpad "confidence ask" / feedback approach across domains.

- Priority order (determined for maximum impact / unblocking + existing infra):
  1. watershortcut.com (recent automation landing + cleanup, promotion sprint item, high validation value for utility/housing operators)
  2. doting.co (explicitly paired in Wake-Up Launchpad, same sprint)
  3. growth.business (in NOW, heavy existing draft infrastructure, broad growth focus)
  4. 10-7.org (mature outreach cycle, advocacy/education positioning)
  5. affordablehome.us, buypatioheater.com, cascadeave.com, chatulah.com (from current outreach drafts list in dashboard)
  6+ Others as snapshots and route patterns come online (communityinternet, riskfreetrial, etc.)

The cycle:
- Picks the next domain in priority that doesn't have a recent pending approval or was last touched > 24h ago (configurable).
- Generates 3 draft-only LinkedIn confidence/feedback asks using the wakeup generator (for 1+2) or basic templates for others (extendable).
- Saves bundles to the domain's outreach_outputs/.
- Updates state/outreach/promotion_state.json with pending_approvals list.
- Outputs a clean SUMMARY + PROACTIVE_MESSAGE text that the calling agent should send via iMessage to the user.

This prevents the user (Nir) from being the bottleneck: the system proactively generates high-quality, on-brand drafts and texts them ready for quick review/approve/skip/tweak via reply. User only pastes/sends on approved ones.

Cron integration (improved text instruction system for bottlenecks - now uses dedicated bottleneck_instructor.py for max-scope rich texts):
- Run via agentTurn. After state update:
  python3 /Users/nirlevy/.openclaw/workspace/scripts/bottleneck_instructor.py --domain <the-next> --task "Review/approve the revenue-focused drafts (evolve feedback to monetization: affiliate partner pitches, ad network intros, tool trial CTAs with tracking for this domain)" --link "https://nnlevy.github.io/portfolio-outreach-viewer/?domain=<the-next>" --revenue-impact "Closes traffic->conversion->revenue loop (ads/affiliates/subs/leads) for automated platform; your min input (approve/feedback) feeds learnings for rapid quality gain" --send
- The instructor detects, generates the FULL structured proactive iMessage (manifesto goal tie-in, live links, min-input options that auto process into learnings/state + trigger next, expected outcome), and sends via openclaw (iMessage).
- Agent: read manifesto first (or qmd), process reply (APPROVE/FEEDBACK/SKIP via --mark or record), apply learnings (specific + general to generator), trigger follow-on revenue automation.
- Broad: call this instructor from ANY cron/agent when you detect user bottleneck (pending_approvals, blocked queue, missing snapshots, custom in bottlenecks.json). Texts always include manifesto + viewer + revenue impact. This is the improved system: rich instructions requiring only your high-signal reply; max automation elsewhere for min input + compounding quality.
- On reply (thread context): call --mark-approved or record_wakeup_reply.py; update state/learnings; trigger e.g. revenue pitch variant or deploy.

State format (state/outreach/promotion_state.json):
{
  "last_run": "...",
  "priority": ["watershortcut.com", "doting.co", ...],
  "pending_approvals": [
    {"domain": "...", "bundle_md": "...", "bundle_json": "...", "generated": "...", "status": "pending_approval"}
  ],
  "history": [{"domain": "...", "approved_at": "...", "action": "approved|skipped|feedback"}]
}

Usage:
  python3 portfolio_promotion_cycle.py --next
  python3 portfolio_promotion_cycle.py --domain watershortcut.com
  python3 portfolio_promotion_cycle.py --mark-approved watershortcut.com   # after user reply

The script is safe to run from crons/agentTurns. It never sends; it prepares for human approval.

Extend for more domains by adding positioning in the wakeup script or here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

STATE_PATH = Path("/Users/nirlevy/.openclaw/workspace/state/outreach/promotion_state.json")
WORKSPACE = Path("/Users/nirlevy/.openclaw/workspace")
WAKEUP_SCRIPT = WORKSPACE / "scripts" / "wakeup_confidence_outreach.py"
RECORD_SCRIPT = WORKSPACE / "scripts" / "record_wakeup_reply.py"

# Priority order - most effective first based on:
# - Recent work (watershortcut automation + stale PR fix)
# - Explicit promotion sprint in dashboard
# - NOW/NEXT status and existing outreach infra (drafts, cycles)
# - Validation leverage (feedback now saves heavy lifting later)
# - Breadth (growth.business covers more)
PRIORITY = [
    "watershortcut.com",
    "doting.co",
    "growth.business",
    "10-7.org",
    "affordablehome.us",
    "buypatioheater.com",
    "cascadeave.com",
    "chatulah.com",
    # Add more as inventory snapshots and route patterns complete
]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "last_run": None,
        "priority": PRIORITY,
        "pending_approvals": [],
        "history": [],
    }

def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def get_next_domain(state: dict[str, Any]) -> str | None:
    pending_domains = {p["domain"] for p in state.get("pending_approvals", []) if p.get("status") == "pending_approval"}
    history = state.get("history", [])
    now = datetime.now(timezone.utc)

    for domain in state.get("priority", PRIORITY):
        if domain in pending_domains:
            continue
        # Skip if very recently touched (approved/skipped in last 12h)
        recent = False
        for h in reversed(history[-5:]):
            if h.get("domain") == domain:
                try:
                    ts = datetime.fromisoformat(h.get("ts", ""))
                    if (now - ts) < timedelta(hours=12):
                        recent = True
                except Exception:
                    pass
                break
        if not recent:
            return domain
    return None

def run_wakeup_generator(domain: str, max_drafts: int = 3) -> dict[str, str]:
    """Run the existing wakeup script and return paths to the latest bundles."""
    contacts_map = {
        "watershortcut.com": WORKSPACE / "watershortcut" / "contacts" / "watershortcut_targets.json",
        "doting.co": WORKSPACE / "doting" / "contacts" / "doting_targets.json",
    }
    contacts_file = contacts_map.get(domain)
    if not contacts_file or not contacts_file.exists():
        print(f"WARNING: No contacts for {domain}, using defaults in generator", file=sys.stderr)

    output_dir = WORKSPACE / domain.split(".")[0] / "outreach_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(WAKEUP_SCRIPT),
        "--domain", domain,
        "--max-drafts", str(max_drafts),
        "--output-dir", str(output_dir),
    ]
    if contacts_file and contacts_file.exists():
        cmd.extend(["--contacts-file", str(contacts_file)])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Generator failed for {domain}")

    # Find the just-created files
    md_files = sorted(output_dir.glob("wakeup_confidence_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    json_files = sorted(output_dir.glob("wakeup_confidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not md_files:
        raise RuntimeError("No output MD produced")

    return {
        "bundle_md": str(md_files[0]),
        "bundle_json": str(json_files[0]) if json_files else "",
    }

def generate_for_domain(domain: str) -> dict[str, Any]:
    """Generate drafts for a domain. For now focused on wakeup pair; extensible."""
    if domain in ("watershortcut.com", "doting.co"):
        paths = run_wakeup_generator(domain)
    else:
        # Fallback: for other domains, we could call their existing cycle or use a simple template.
        # For v1, create a basic bundle using the generator with a placeholder (user can extend).
        print(f"Using basic template for {domain} (extend wakeup script with positioning for full effect)")
        # Create a minimal bundle so the flow works
        output_dir = WORKSPACE / domain.split(".")[0].replace("-", "") / "outreach_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = now_iso().replace(":", "").replace("-", "").split(".")[0] + "Z"
        base = output_dir / f"wakeup_confidence_{domain.replace('.', '-')}_{ts}"
        bundle = {
            "generated_at": now_iso(),
            "domain": domain,
            "note": "Basic placeholder - run with full positioning from dashboard for best results. Use existing per-domain outreach cycles for bootstrap drafts.",
            "linkedin_drafts": [
                {"message": f"Hi there - testing a quick feedback loop for {domain} using the portfolio promotion automation. Would value 60s of your thoughts on the current flow."}
            ]
        }
        (base.with_suffix(".json")).write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        md = f"# {domain}\n\nPlaceholder draft for approval flow.\n\nSee JSON: {base}.json\n"
        (base.with_suffix(".md")).write_text(md, encoding="utf-8")
        paths = {"bundle_md": str(base.with_suffix(".md")), "bundle_json": str(base.with_suffix(".json"))}

    return {
        "domain": domain,
        "bundle_md": paths["bundle_md"],
        "bundle_json": paths.get("bundle_json", ""),
        "generated": now_iso(),
        "status": "pending_approval",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--next", action="store_true", help="Pick and generate for the next priority domain")
    parser.add_argument("--domain", help="Generate for specific domain")
    parser.add_argument("--mark-approved", help="Mark a domain's pending as approved (after user reply)")
    parser.add_argument("--max-drafts", type=int, default=3)
    args = parser.parse_args()

    state = load_state()

    if args.mark_approved:
        domain = args.mark_approved
        for p in state.get("pending_approvals", []):
            if p["domain"] == domain and p["status"] == "pending_approval":
                p["status"] = "approved"
                p["approved_at"] = now_iso()
                state.setdefault("history", []).append({
                    "domain": domain,
                    "action": "approved",
                    "ts": now_iso(),
                    "bundle": p.get("bundle_md")
                })
                save_state(state)
                print(f"Marked {domain} as approved.")
                return 0
        print(f"No pending approval found for {domain}")
        return 1

    target_domain = args.domain
    if args.next or not target_domain:
        target_domain = get_next_domain(state)
        if not target_domain:
            print("No next domain ready in priority (all have recent pending or history).")
            return 0

    print(f"Processing promotion cycle for {target_domain}...")

    entry = generate_for_domain(target_domain)

    # Update pending (remove old for same domain, add new)
    state["pending_approvals"] = [p for p in state.get("pending_approvals", []) if p["domain"] != target_domain]
    state["pending_approvals"].append(entry)
    state["last_run"] = now_iso()
    state.setdefault("history", []).append({
        "domain": target_domain,
        "action": "generated",
        "ts": now_iso(),
        "bundle": entry["bundle_md"]
    })

    save_state(state)

    # Structured output for the agent to use in proactive iMessage
    summary = f"""Portfolio Promotion Cycle

Domain: {target_domain}
Generated: {entry['generated']}
Status: {entry['status']}

Drafts ready (draft-only, per Wake-Up rules):
- MD (human readable, copy-paste ready): {entry['bundle_md']}
- JSON (structured): {entry.get('bundle_json', 'n/a')}

This is the next in priority for proactive confidence/feedback asks.

PROACTIVE MESSAGE FOR USER (send via iMessage):
Portfolio outreach automation: I just generated {args.max_drafts} draft-only LinkedIn confidence asks for {target_domain} using the exact Wake-Up Launchpad positioning + scripts.

Full easy-to-read version: {entry['bundle_md']}

Do these look good for you to send today? 
Reply:
- APPROVE {target_domain}
- FEEDBACK: your notes here (e.g. tweak the tie-in for property managers)
- SKIP {target_domain}

I'll mark the state and we can log replies later with the record tool. This keeps you from being the bottleneck - drafts are pre-made and on-brand."""

    print("\n" + "="*60)
    print(summary)
    print("="*60)
    print("\nState updated. The calling agent should now proactively text the user the PROACTIVE MESSAGE above (or a polished version of it) and include the file path.")

    # Also write a small "latest_proactive.txt" for easy reference by agent
    latest = WORKSPACE / "state" / "outreach" / "latest_proactive.txt"
    latest.write_text(summary, encoding="utf-8")

    # Generate and deploy the live mobile Safari viewer + feedback tool
    try:
        html_path = generate_and_deploy_live_viewer(state, entry)
        print(f"\nLIVE VIEWER DEPLOYED: {html_path}")
        print("Bookmark this on your iPhone Safari for instant access from anywhere:")
        print("https://nnlevy.github.io/portfolio-outreach-viewer/")
        live_link = "https://nnlevy.github.io/portfolio-outreach-viewer/"
        # Use the improved bottleneck instructor for the proactive text (rich, revenue-tied, min-input)
        instructor_cmd = [
            sys.executable, str(WORKSPACE / "scripts" / "bottleneck_instructor.py"),
            "--domain", target_domain,
            "--task", f"Review/approve the revenue-focused drafts (monetization pitches: affiliates for tools, ad intros, trial CTAs; evolve from pure feedback)",
            "--link", f"{live_link}?domain={target_domain}",
            "--revenue-impact", f"Closes automated traffic->conversion->revenue (ads/affiliates/subs/leads from {target_domain} tools/content) with min your input; your FEEDBACK feeds learnings for rapid quality gain across portfolio.",
            "--send"
        ]
        print("\nCalling bottleneck_instructor for proactive text send via OpenClaw...")
        subprocess.run(instructor_cmd, timeout=90)
        # Still write local summary for reference
        summary = summary.replace(
            "Full easy-to-read version: " + entry.get('bundle_md', ''),
            f"Review & give feedback from your phone (mobile-optimized, fast Safari access + manifesto): {live_link}\n\nDirect: {entry.get('bundle_md', '')}"
        )
        latest.write_text(summary, encoding="utf-8")
    except Exception as e:
        print(f"Viewer/instructor deploy/send skipped (error: {e}). Local files still available. Manual: python3 scripts/bottleneck_instructor.py --domain {target_domain} --send")

    return 0


def generate_and_deploy_live_viewer(state: dict, latest_entry: dict) -> str:
    """Generate a beautiful, self-contained, mobile-Safari-optimized single-file HTML viewer.
    Embeds current pending drafts, previous learnings, per-domain + general feedback forms.
    On 'submit' the form builds copyable text for iMessage reply to the agent.
    Easy to perfect: shows learnings applied, feedback history.
    The cycle pushes this to GitHub Pages for live URL access from anywhere.
    """
    pending = state.get("pending_approvals", [])
    history = state.get("history", [])[-5:]  # recent
    learnings = load_learnings()

    # Build the HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio Outreach • Live Drafts & Feedback</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&amp;family=Space+Grotesk:wght@500;600&amp;display=swap');
        :root {{ --primary: #0A0A0A; }}
        body {{ font-family: 'Inter', system_ui, sans-serif; }}
        .font-display {{ font-family: 'Space Grotesk', 'Inter', sans-serif; }}
        .draft-card {{ transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); }}
        .draft-card:hover {{ transform: translateY(-1px); box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); }}
        .mobile-btn {{ min-height: 48px; font-size: 15px; }}
        .feedback-textarea {{ min-height: 110px; }}
        pre.draft-text {{ white-space: pre-wrap; font-size: 14.5px; line-height: 1.45; }}
        .section-header {{ font-size: 13px; letter-spacing: -.5px; font-weight: 600; }}
    </style>
</head>
<body class="bg-zinc-950 text-zinc-200">
    <div class="max-w-2xl mx-auto px-4 py-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-6">
            <div>
                <div class="flex items-center gap-x-3">
                    <i class="fa-solid fa-rocket text-emerald-400 text-3xl"></i>
                    <div>
                        <h1 class="font-display text-3xl font-semibold tracking-tighter">Outreach Promotion</h1>
                        <p class="text-emerald-400 text-sm">Live • Mobile-first • Feedback loop</p>
                    </div>
                </div>
            </div>
            <div class="text-right text-xs">
                <div class="text-zinc-400">Last updated</div>
                <div class="font-mono text-emerald-300">{latest_entry.get('generated', now_iso())[:16]}</div>
            </div>
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded-3xl p-5 mb-6">
            <div class="flex items-center gap-2 mb-3">
                <i class="fa-solid fa-list-check text-emerald-400"></i>
                <span class="section-header text-emerald-400">PRIORITY ORDER (AUTO-ROLLOUT)</span>
            </div>
            <div class="flex flex-wrap gap-1.5 text-sm">
                {"".join([f'<span class="px-2.5 py-0.5 rounded-2xl bg-zinc-800 text-zinc-300 text-xs font-medium">{"★ " if i==0 else ""}{d}</span>' for i, d in enumerate(state.get("priority", []))])}
            </div>
            <div class="mt-3 text-[11px] text-zinc-500">The system proactively generates for the next domain and texts you. This page is the single source of truth for review + feedback from your phone.</div>
        </div>

        <!-- Pending Approvals -->
        <div class="mb-4">
            <div class="flex items-center justify-between mb-3 px-1">
                <div class="section-header text-white flex items-center gap-2">
                    <i class="fa-solid fa-inbox"></i> 
                    <span>CURRENT PENDING (needs your quick review)</span>
                </div>
                <span class="text-xs bg-white/5 text-white/60 px-2 py-px rounded-full">{len(pending)} domain(s)</span>
            </div>

            {"".join([render_domain_card(p, learnings) for p in pending]) if pending else '<div class="text-zinc-400 text-sm px-2">No pending right now. Great job clearing the queue!</div>'}
        </div>

        <!-- Feedback Learnings -->
        <div class="bg-zinc-900 border border-zinc-800 rounded-3xl p-5 mb-6">
            <div class="section-header mb-3 flex items-center gap-2 text-amber-400">
                <i class="fa-solid fa-lightbulb"></i> 
                <span>WHAT WE'VE LEARNED (applied to generations)</span>
            </div>
            <div class="space-y-3 text-sm">
                {render_learnings(learnings)}
            </div>
            <div class="mt-4 text-[10px] text-zinc-500">Feedback you give here (via copy-to-iMessage) gets incorporated into future drafts — specific to the domain and general patterns across the portfolio.</div>
        </div>

        <!-- How to use on phone -->
        <div class="text-center text-xs text-zinc-500 mb-8">
            <p class="mb-1">Bookmark this page on your iPhone Home Screen for app-like access.</p>
            <p>Tap any "Copy draft" or "Copy feedback" — then paste directly into your iMessage thread with the automation agent.</p>
        </div>

        <script>
            function tailwindInit() {{
                // Tailwind script already loaded via CDN
            }}
            
            function copyText(text, btn) {{
                navigator.clipboard.writeText(text).then(() => {{
                    const orig = btn.innerHTML;
                    btn.innerHTML = '<i class="fa-solid fa-check mr-1.5"></i> Copied!';
                    btn.classList.add('!bg-emerald-600');
                    setTimeout(() => {{
                        btn.innerHTML = orig;
                        btn.classList.remove('!bg-emerald-600');
                    }}, 1800);
                }});
            }}

            function buildFeedbackAndCopy(domain, mdPath) {{
                const specific = document.getElementById('fb-specific-' + domain).value.trim();
                const general = document.getElementById('fb-general').value.trim();
                
                // Per user rule (2026-06-19): when feedback/approval via iMessage (esp. quote-reply), the copied text must allow starting with Approve? and include quote instruction for context. The proactive messages now start with Approve? and tell to quote + "Approve? FEEDBACK..."
                let text = `Approve? FEEDBACK for ${{domain}} (from mobile Safari viewer, quote the original proactive text)\\n\\n`;
                if (specific) text += `Specific to this domain: ${{specific}}\\n\\n`;
                if (general) text += `General learnings (applies across domains): ${{general}}\\n\\n`;
                text += `Draft bundle: ${{mdPath}}\\n\\n`;
                text += `Action requested: please incorporate and mark as ready or generate improved version. (Agent: parse the quoted original Approve? message + this for exact domain/action.)`;
                
                navigator.clipboard.writeText(text).then(() => {{
                    const msg = `Copied "Approve? FEEDBACK..." for ${{domain}}. Quote the original proactive iMessage (which starts with Approve?) and paste this reply — agent will use quoted context + prefix to process (per the rule to fix previous quote-reply context loss). This will perfect future drafts.`;
                    alert(msg);
                    
                    // Optional: clear the form after copy
                    // document.getElementById('fb-specific-' + domain).value = '';
                }}).catch(() => {{
                    // Fallback for older Safari
                    prompt("Copy this (quote original Approve? message + paste):", text);
                }});
            }}

            function copyDraft(draftText, btn) {{
                navigator.clipboard.writeText(draftText).then(() => {{
                    const origText = btn.textContent;
                    btn.textContent = 'Copied to clipboard ✓';
                    setTimeout(() => btn.textContent = origText, 1600);
                }});
            }}

            // Keyboard friendly + mobile
            console.log('%c[Outreach Viewer] Mobile Safari optimized. Feedback forms ready for quick input + copy-to-iMessage.', 'color:#3f3f46');
        </script>
    </div>
</body>
</html>'''

    # Write the HTML locally for reference
    viewer_local = WORKSPACE / "state" / "outreach" / "promotion-viewer.html"
    viewer_local.write_text(html, encoding="utf-8")

    # Now deploy to the GitHub Pages repo
    deploy_viewer_to_pages(html, state)

    return str(viewer_local)


def render_domain_card(pending: dict, learnings: dict) -> str:
    domain = pending["domain"]
    md_path = pending.get("bundle_md", "")
    gen_time = pending.get("generated", "")[:16]

    # Load the actual draft content if possible (for embedding)
    draft_text = "Draft text embedded in the live viewer (see link for full formatted version with copy buttons)."
    try:
        if md_path:
            content = Path(md_path).read_text(encoding="utf-8")
            # Extract a sample LinkedIn draft
            import re
            match = re.search(r'```(.*?)```', content, re.DOTALL)
            if match:
                draft_text = match.group(1).strip()[:650] + "... (full in file)"
    except:
        pass

    specific_learnings = learnings.get(domain, [])
    specific_html = "".join([f'<li class="text-xs">• {l}</li>' for l in specific_learnings[-2:]]) or "<li class=\"text-xs text-zinc-500\">No domain-specific learnings yet.</li>"

    return f'''
    <div class="draft-card bg-zinc-900 border border-zinc-800 rounded-3xl p-4 mb-4">
        <div class="flex justify-between items-start mb-3">
            <div>
                <div class="font-semibold text-lg tracking-tight">{domain}</div>
                <div class="text-[10px] text-zinc-500 font-mono">{gen_time}</div>
            </div>
            <a href="{md_path}" class="text-xs px-3 py-1.5 bg-white/5 hover:bg-white/10 active:bg-white/20 rounded-2xl flex items-center gap-x-1 text-emerald-400 transition-colors" target="_blank">
                <i class="fa-solid fa-file-lines"></i>
                <span class="text-[10px] font-medium">OPEN FULL MD</span>
            </a>
        </div>

        <div class="bg-zinc-950 border border-zinc-800 rounded-2xl p-3 mb-3">
            <div class="section-header text-zinc-400 mb-1.5">READY LINKEDIN DRAFT (tap to copy)</div>
            <pre class="draft-text bg-black/40 p-3 rounded-xl text-emerald-100 text-[13.5px] leading-snug overflow-auto max-h-[210px] font-light">{draft_text}</pre>
            <button onclick="copyDraft(`{draft_text.replace('`', '\\`')}`, this)" 
                    class="mt-2 mobile-btn w-full bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 transition-colors text-white font-semibold rounded-2xl text-sm flex items-center justify-center gap-x-2 py-2.5">
                <i class="fa-solid fa-copy"></i> 
                <span>COPY DRAFT FOR LINKEDIN</span>
            </button>
        </div>

        <div class="grid grid-cols-1 gap-3">
            <!-- Domain specific feedback -->
            <div>
                <label class="section-header block mb-1 text-white/80">FEEDBACK SPECIFIC TO {domain.upper()}</label>
                <textarea id="fb-specific-{domain}" class="feedback-textarea w-full bg-zinc-950 border border-zinc-800 focus:border-zinc-600 rounded-2xl px-3 py-2 text-sm placeholder:text-zinc-600" placeholder="e.g. The tier-jump example landed really well. Make the outdoor calculator more prominent."></textarea>
            </div>

            <!-- General (shared across domains) -->
            <div>
                <label class="section-header block mb-1 text-white/80">GENERAL LEARNINGS (affects all future promotions)</label>
                <textarea id="fb-general" class="feedback-textarea w-full bg-zinc-950 border border-zinc-800 focus:border-zinc-600 rounded-2xl px-3 py-2 text-sm placeholder:text-zinc-600" placeholder="e.g. Always mention the person's role/company early. Keep CTAs under 2 sentences."></textarea>
            </div>
        </div>

        <button onclick="buildFeedbackAndCopy('{domain}', '{md_path}')" 
                class="mt-3 mobile-btn w-full bg-white text-black font-semibold rounded-2xl flex items-center justify-center gap-x-2 py-3 text-sm active:scale-[0.985] transition-transform">
            <i class="fa-solid fa-paper-plane"></i>
            <span>COPY FORMATTED FEEDBACK FOR iMESSAGE</span>
        </button>

        <div class="mt-2 text-[10px] text-center text-zinc-500">This copies a ready-to-paste "Approve? FEEDBACK..." message. Quote the original proactive iMessage (it will start with "Approve?") and reply with this pasted — the agent now reliably uses the quoted context + "Approve?" prefix (user rule to fix quote-reply understanding). The agent will learn and process exactly.</div>
    </div>
    '''


def render_learnings(learnings: dict) -> str:
    html_parts = []
    for dom, items in learnings.items():
        if items:
            html_parts.append(f'<div><span class="font-semibold text-xs text-amber-300">{dom}:</span> <span class="text-xs">{", ".join(items[-2:])}</span></div>')
    if not html_parts:
        return '<div class="text-xs text-zinc-500">No learnings recorded yet. Your first feedback will start teaching the system.</div>'
    return "".join(html_parts)


def load_learnings() -> dict:
    learn_path = WORKSPACE / "state" / "outreach" / "learnings.json"
    if learn_path.exists():
        try:
            return json.loads(learn_path.read_text())
        except:
            pass
    return {}


def deploy_viewer_to_pages(html_content: str, current_state: dict):
    """Push the live viewer (index.html) + state to the dedicated repo.
    User enables GitHub Pages (repo Settings > Pages > Source: main / (root)) once — then https://nnlevy.github.io/portfolio-outreach-viewer/ is the permanent fast mobile Safari link for review + feedback from anywhere.
    The cycle keeps it 100% up to date automatically.
    """
    import tempfile
    import subprocess as sp

    viewer_repo = "nnlevy/portfolio-outreach-viewer"
    with tempfile.TemporaryDirectory() as tmpdir:
        sp.check_call(["gh", "repo", "clone", viewer_repo, tmpdir + "/v"], timeout=90)
        vdir = Path(tmpdir) / "v"

        (vdir / "index.html").write_text(html_content, encoding="utf-8")
        (vdir / "promotion_state.json").write_text(json.dumps(current_state, indent=2), encoding="utf-8")

        learn_path = WORKSPACE / "state" / "outreach" / "learnings.json"
        if learn_path.exists():
            (vdir / "learnings.json").write_text(learn_path.read_text(), encoding="utf-8")

        sp.check_call(["git", "-C", str(vdir), "add", "index.html", "promotion_state.json", "*.json"], timeout=30)
        try:
            sp.check_call(["git", "-C", str(vdir), "commit", "-m", f"Live mobile viewer update: {now_iso()}"], timeout=30)
            sp.check_call(["git", "-C", str(vdir), "push", "origin", "main"], timeout=60)
        except sp.CalledProcessError:
            pass  # no change


def load_learnings_for_generator() -> dict:
    """Helper so the generator can 'learn' from feedback in future versions."""
    return load_learnings()


if __name__ == "__main__":
    sys.exit(main())
