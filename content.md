---
layout: content
title: Content
eyebrow: AI video and the work behind it
description: "The AI video work of Dr Xanqunnes Nursingh: how a serialised AI comedy is made, the output and the production stack, and earlier work."
dek: A serialised AI comedy made with Veo 3, with the output, the production stack and the numbers in one place.
facts: [m2-articles, m2-carousels, m2-longform, m2-visitors, m2-likes, m2-profile-views, series-seasons, series-reach, series-subs, series-ceiling, series-top3, video-views-1, video-views-2, video-views-3, best-format, persona-views, m2-videos, m2-linkedin, m2-impressions, m2-tiktok, m2-youtube, pmg-sheets]
---
<div class="evidence-row">
{% include evidence.html id="series-reach" %}
{% include evidence.html id="series-subs" %}
{% include evidence.html id="series-ceiling" %}
</div>

<div class="prose" markdown="1">

## The Mafia Cats

The Mafia Cats is a serialised AI comedy with {% include fact.html id="series-seasons" %}. As of 5 Oct 2026 it has {% include fact.html id="series-reach" %}, and the channel has {% include fact.html id="series-subs" %}. It has run since 21 Oct 2025 on [the series channel](https://www.youtube.com/@meowmmedia){:rel="noopener noreferrer"}.

## How it is made

I make AI video with Veo 3, edit in CapCut Pro, use ElevenLabs for voice, and run a local container of open-source audio models for music and effects.

The pipeline is layered shot assembly built from character and location records. The desktop app in [AI Studio Tool]({{ '/work/ai-studio-tool/' | relative_url }}) is the software that does it.

A separate AI persona series, kept visually consistent with a LoRA I trained locally, {% include fact.html id="persona-views" %} (creator-reported).

## Featured videos

Three videos from the series, with views as of 5 Oct 2026. For scale: {% include fact.html id="series-ceiling" %}.

- ["The Sky's New King Doesn't Negotiate"](https://www.youtube.com/watch?v=Y7XaDXi2uto){:rel="noopener noreferrer"}, 10 Feb 2026, {% include fact.html id="video-views-1" %}.
- ["When animal control RAIDS your crew..."](https://www.youtube.com/watch?v=TvoqKL0XdSo){:rel="noopener noreferrer"}, 19 Jan 2026, {% include fact.html id="video-views-2" %}.
- ["Finally A "Made" Man (And the Mafia has a new Secret Weapon)"](https://www.youtube.com/watch?v=TC07BMTST0A){:rel="noopener noreferrer"}, 4 Mar 2026, {% include fact.html id="video-views-3" %}.

## What performed best {#numbers}

The best performers were story episodes of {% include fact.html id="best-format" %}, published from January to early March 2026, and the three most-watched videos reached {% include fact.html id="series-top3" %}.

What I would do next: weight the schedule toward the short story format that performed, and treat every change as a test against retention and click-through before adding volume.

## Content before AI {#earlier}

Before I made AI video, I made live-action content. From Jan to Sep 2024 I was Director of Communications at M2 Biosciences, a biosciences company, working across LinkedIn, TikTok and YouTube. I wrote, recorded and fronted it myself.

- {% include fact.html id="m2-videos" %} (creator-reported), with the scripting, set and equipment, recording and platform-specific edits done by me.
- {% include fact.html id="m2-articles" %}, {% include fact.html id="m2-carousels" %} and {% include fact.html id="m2-longform" %} that turned complex biosciences research into accessible content.
- A recurring series called Wellness Friday, built on practical, science-based health guidance.
- Content production standards and platform compliance workflows, community engagement and moderation, and outreach to doctors and medical staff for product demonstrations and partnerships.

The platform changes below are creator-reported, from 2024, and no base figures were recorded.

{% assign m2_rows = "m2-linkedin,m2-impressions,m2-visitors,m2-tiktok,m2-likes,m2-profile-views,m2-youtube" | split: "," %}
{% include ledger.html ids=m2_rows caption="Platform changes at M2 Biosciences, creator-reported" %}

## Public tool and cheat sheets

I built [Prompt Master G]({{ '/work/prompt-master-g/' | relative_url }}), a free tool for structured Veo 3 prompts, and published {% include fact.html id="pmg-sheets" %} beside it. The tool is live at [veopromptai.netlify.app](https://veopromptai.netlify.app){:rel="noopener noreferrer"}.

</div>
