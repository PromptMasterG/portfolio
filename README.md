# Portfolio of Dr Xanqunnes Nursingh

This repository builds the portfolio site for Dr Xanqunnes Nursingh, an AI engineer and AI content creator.
Once it is public, the site is at https://promptmasterg.github.io/portfolio/.

The work shown on the site is closed-source, so this repository holds no code, prompts, schemas, configurations
or raw art from it, only descriptions, dated measurements and the supplied screenshots. A leak scan in the
continuous integration checks every pull request for fenced code, unlisted images, paths, secret-shaped
strings and similar slips, and the site is walked through live on request.

## What is in here

- Pages written in Markdown, rendered by Jekyll with the same plugin set GitHub Pages uses.
- Every number on the site lives in one data file with a label, a date, a claim reference and any qualifier,
  and pages render it from there.
- Checks for leaks, structure, links, accessibility and performance, run on every pull request.
- A profile README for the special profile repository, kept in its own folder, to be copied by hand.

## Notes

- The pages carry noai and noimageai meta tags, and the robots rules allow normal indexing. These are
  requests to crawlers, not guarantees.
- The site makes no third-party requests, sets no cookies and has no analytics.
- Accessibility: the checks report what an automated tool and a keyboard walk-through found. They are not a
  conformance claim.
- Licence: all rights reserved, view for evaluation only. See the licence file.
