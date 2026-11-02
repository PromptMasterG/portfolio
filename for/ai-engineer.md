---
layout: page
title: For AI engineering roles
eyebrow: One page for applications
description: A one-page summary for AI engineer and AI developer roles from Dr Xanqunnes Nursingh, with a fit checklist and links to the evidence behind each line.
dek: "The short version for a hiring manager: what I build, how it was verified, and where each claim can be checked."
facts: [samara-tps-gpu, samara-cache-reuse, mcs-collections, studio-tools, samara-suite-pass, tests-total, samara-prefill-error, samara-ts-lines, signal-passes]
---
<div class="prose" markdown="1">

## The pitch

I build and evaluate applied AI systems: local model inference, retrieval behind a grounding gate, and agents behind an MCP server. I measure before I adopt anything, and I publish my own [corrections]({{ '/how-i-build/#correct' | relative_url }}). I work with Claude Code under written specifications and test gates, and I verify what comes back.

I trained as a doctor, and the safety work sits beside the evaluation work: a crisis screen that does not depend on the model, and an ethics audit of companion-app harms, both in [Samara]({{ '/work/samara/' | relative_url }}).

</div>

## Fit checklist

{% include fit-list.html role="engineer" %}

## Three best proof items

<div class="evidence-row">
{% include evidence.html id="samara-suite-pass" %}
{% include evidence.html id="samara-tps-gpu" %}
{% include evidence.html id="samara-prefill-error" %}
</div>

<div class="prose" markdown="1">

All three come from the [Samara case study]({{ '/work/samara/#verification' | relative_url }}). The test counts behind the other projects are explained, codebase by codebase, on [How I build]({{ '/how-i-build/#tests' | relative_url }}).

## Credentials in AI engineering

As I list them.

{% include credentials.html set="ai" %}

## Contact

[{{ site.data.profile.email }}](mailto:{{ site.data.profile.email }}). CV on request. {{ site.data.profile.availability }}

</div>
