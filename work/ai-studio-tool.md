---
layout: case-study
title: AI Studio Tool
project: ai-studio-tool
wide: true
description: "AI Studio Tool is a closed-source MCP server with an orchestrator and ten specialist agents for a YouTube channel, shown beside a separate desktop app."
dek: An MCP server that gives any agent an orchestrator and ten specialists to run a YouTube channel, and a separate desktop app that holds the records and prompts for a real series.
og_image: assets/ai-studio-tool/dashboard.png
screens:
  - assets/ai-studio-tool/dashboard.png
role: Specifier, designer and verifier. Built with Claude Code under my written plan, acceptance criteria and test gates.
period: Active. Counts taken on 1 Nov 2026.
stack: Python MCP server and Tauri observatory in React and TypeScript; a desktop app on FastAPI, React, Tailwind, SQLite and ChromaDB.
scale: [studio-py-lines]
key_facts: [studio-tools, studio-agents, studio-tests, mcs-collections]
ledger_server: [studio-tools, studio-agents, studio-py-lines, studio-tests, studio-commits, studio-writes]
ledger_app: [mcs-library, mcs-collections, mcs-mcp, mcs-turnaround, mcs-assets, mcs-lines, mcs-tests]
facts: [studio-tools, studio-agents, studio-py-lines, studio-tests, studio-commits, studio-writes, mcs-characters, mcs-locations, mcs-scripts, mcs-labs, mcs-library, mcs-collections, mcs-mcp, mcs-turnaround, mcs-assets, mcs-lines, mcs-tests]
---
## The problem

A general-purpose agent knows nothing about one channel's voice, audience or past results unless someone supplies it every time, and a video model forgets a cast between episodes. I wanted an agent that arrives briefed, spends only what it may, and learns from the channel's own numbers.

## What it does

- Gives any MCP-capable agent a way to run a channel through {% include fact.html id="studio-tools" %}.
- Builds a brief for every request from the channel's voice, audience and past corrections.
- Offers a free default path, where the connecting agent writes from the brief, and an opt-in paid path under hard spend ceilings.
- Versions and checksums everything it saves, with an audit log.
- Feeds the strongest hooks and titles from published videos back as examples for the next brief.

## The orchestrator and its specialists {#agents}

Behind the server sit {% include fact.html id="studio-agents" %}. Each card names a role, says what it is for and shows a screen. For Scout, Strategist, Manager, Publisher and SEO the line is the wording of the Studio Deck's own panel for that role. The other five lines are my plain-words reading of the role, and their screens are the closest ones in the desktop app, so the pairing is not a wiring diagram.

{% include team.html %}

{% include figure.html file="assets/ai-studio-tool/studio-deck-org.png" %}

## The Mafia Cats as the worked example {#example}

The Mafia Cats is a serialised AI comedy made with Veo 3, so it tests what the tool is for: the same cast and places across many episodes. The desktop app holds its {% include fact.html id="mcs-library" %} as structured records, assembles each prompt in layers, and warns when channel metrics are stale. Its documentation tells agents to query a knowledge store of {% include fact.html id="mcs-collections" %} before they generate. The server and the app are separate programs. They share no code and do not call each other, and the series reaches the server only through an explicit import into a channel workspace.

## How it works {#how}

```mermaid
flowchart TD
  A[Request from an agent or the app] --> B[Orchestrator]
  B --> C[Brief builder]
  C --> D[Channel records and knowledge lookup]
  D --> E[Specialist does the work]
  E --> G[Versioned save and audit trail]
  G --> H[Performance analysis]
  H --> I[Examples for the next brief]
```

<p class="figcap">Components and data flow, in plain English. The lookup comes first, every time.</p>

A request reaches the orchestrator, which asks the brief builder for context from the channel's own workspace. The lookup comes before any generation, and the stored record is always used. A specialist does the work, and everything saved is versioned. Performance data then feeds the next brief.

## Decisions and trade-offs

**Lookup before generation.** A forced query costs a round trip, which composite calls recover. In exchange, a scene starts from the record.

**Briefs instead of blind prompts.** The price is the work of keeping the channel's records accurate.

**A small tool catalogue.** It protects the connecting agent's context window, with the full manual fetched on demand.

**Physical isolation between channels.** Each channel has its own workspace and learning store, with no read path between them.

**Labelled heuristics and visible gaps.** The built-in quality check is a deterministic heuristic and is labelled as one, after I removed an LLM judge. The Studio Deck's server defines {% include fact.html id="studio-writes" %}, so the documentation is behind the code.

## Verification and results {#verification}

{% include ledger.html ids=page.ledger_server caption="AI Studio Tool agent server evidence ledger" %}

{% include ledger.html ids=page.ledger_app caption="AI Studio Tool desktop app evidence ledger" %}

The two codebases are counted separately, and no figure is added across them on this page. The production figures are mine and self-measured. The Deck's own TypeScript tests are not in the counts.

## What went wrong and what I corrected

An audit of the core loop found silent defects. I fixed each one and added a regression test. The documentation also went stale once, with the tool count no longer matching the code, so I corrected it. The production speed-up is my own measurement with no baseline, so I cannot say by how much.

## Skills this demonstrates

- Agents and MCP, with spend ceilings that stop a run.
- Retrieval over a multi-collection knowledge store.
- AI video production with structured cast and location records and layered prompt compilers.
- Full-stack delivery across Python, React, Tailwind, SQLite and Tauri, directed and verified by me and written with Claude Code.

## What I would do next

- Recount the tool catalogue and the specialist roster on a schedule.
- Add automated continuity checks. Today continuity is guidance in the agent playbooks, not a check.
- Record a walkthrough of the specialists running end to end, since most screens here are shown before a run.

## Access {#access}

<div class="access" markdown="1">
The source is private. I am happy to walk through it live.
</div>
