---
layout: page
title: How I build
eyebrow: The page that stands in for the code
description: "How Dr Xanqunnes Nursingh builds and verifies AI systems with Claude Code: written specifications, deterministic gates, measured decisions, public corrections."
dek: Because the code is private, this page is the next best thing to reading it. It lists the working rules I apply to every project, each with a real example and what it measured.
facts: [samara-tps-gpu, samara-tps-cpu, samara-cache-reuse, samara-prefill-estimate, samara-prefill-prompt, samara-prefill-actual, samara-prefill-error, samara-adversarial, recheck-sources, recheck-errors, samara-tests, studio-tests, mcs-tests, tests-total]
---
<div class="prose" markdown="1">

## How I work with Claude Code

I build with Claude Code. I write the specification, set the acceptance gates, review the results and decide what ships. The agents write the code under that specification, and I treat what they report as a claim until I have run the software, read the test output or compared the result with a source.

## The practices

### 1. Spec first {#spec}

Every project starts as a written plan in numbered phases, with acceptance criteria for each phase. Anything that is not in the plan goes to a backlog and not into the code. Samara ran on research rounds covering companion ethics, crisis verification, compliance and local-model optimisation, and each round was integrated only after its findings had been checked.

### 2. The model proposes, code disposes {#gate}

Anything a model produces that becomes stored state passes a deterministic gate first. In Samara, a callback may reference only retrieved text, a post-check rejects replies that cite specifics nobody retrieved, and a biography chapter needs entry receipts and verbatim quotes. Every structured model call is grammar-constrained. My rule is that the model never produces a number, so in AI Studio Tool the packaging score is computed by the server and never trusted from the agent's arithmetic.

### 3. Measure before adopting, and log what you decline {#measure}

Four decisions from the engine work in Samara:

- **N-gram speculation, declined.** On CPU, where generation runs at {% include fact.html id="samara-tps-cpu" %}, it accepted no draft tokens.
- **A different quantised checkpoint, measured and declined.**
- **Draft prefill warming, built, measured and reverted,** because the latency it targeted did not exist.
- **A multi-token drafter, adopted on the full-GPU tier only,** after I measured each hardware tier on its own. On the GPU the engine measured {% include fact.html id="samara-tps-gpu" %}.

Keeping the start of every prompt stable is why a warm call reached {% include fact.html id="samara-cache-reuse" %}. That is one measured call, not an average. I leave out the settings and the comparison tables, since together they would be a tuning recipe, and the outcomes above are what matter.

### 4. Correct yourself in public {#correct}

I estimated CPU prompt processing at {% include fact.html id="samara-prefill-estimate" %} for a {% include fact.html id="samara-prefill-prompt" %} prompt, extrapolating from generation speed. Measuring gave {% include fact.html id="samara-prefill-actual" %}. The estimate was off by {% include fact.html id="samara-prefill-error" %}, and I amended the plan on 3 Aug 2026.

### 5. Test the ethics, not only the code {#ethics}

Samara is a companion-style app, so I wrote adversarial cases against its guardrails: {% include fact.html id="samara-adversarial" %}. I fixed both and re-ran the cases. Letters and callbacks refer to content and never to attendance, so there is no guilt for a missed day, and voice changes ship with plain-language release notes because a sudden change of persona is a documented harm in companion apps.

### 6. Verify in the running app {#running}

Passing tests do not show that software works for someone else. A clean-machine audit of Samara hunted for works-on-my-machine assumptions, and the bugs it found had nothing to do with the machine. The acceptance test for its privacy promise is a full session in airplane mode. Signal's first version was checked only through code and never looked at, and it was rejected as boring and hard to use. Its project rules now require a real browser check.

### 7. Fail visibly, spend deliberately {#fail}

AI Studio Tool has hard monthly and per-run spend ceilings that stop a run instead of warning about it. The Studio Deck's blank panels always carry a stated reason, and it says whether it is attached to the live process or showing a snapshot. The built-in quality check is a deterministic heuristic and is labelled as one, after I removed an LLM judge and replaced it with that.

### 8. Check AI output against sources {#sources}

When I re-checked {% include fact.html id="recheck-sources" %} behind lessons an AI had drafted for an app I'm building, I found {% include fact.html id="recheck-errors" %}, so I check the source before a claim goes out. One of them was a reversed meta-analysis finding. I fixed all of them.

### 9. Write for the next session {#next-session}

Each project keeps its plans, manifests, ledgers and runbooks so that a fresh agent or a person can pick it up without me. The manifest also holds the rules for what has to be checked before anything counts as done.

## Counting the tests {#tests}

{% assign test_rows = "samara-tests,studio-tests,mcs-tests,tests-total" | split: "," %}
{% include ledger.html ids=test_rows caption="Automated tests by codebase" %}

The headline figure on the home page is the sum of the first three rows. These are counts of test declarations and not a pass rate, and they leave out Signal and the Studio Deck.

## Questions I would welcome in an interview

- Why did n-gram speculation fail on CPU, and how did you know?
- What does the grounding check do when a reply cites something that was not retrieved?
- How did you find the prompt-processing error, and what changed in the plan?
- What happens mid-run when a spend ceiling is reached?
- Which adversarial case found a real defect, and what did the fix change?
- Can you show the persona case that did not pass, and say how you would fix it?
- What did you reject from an agent's work, and how did you decide?

</div>
