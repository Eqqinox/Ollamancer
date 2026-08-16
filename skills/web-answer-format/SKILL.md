---
name: web-answer-format
description: Shape a web-search answer into organised sections that match what was asked — news briefings, comparisons, how-tos, prices/specs, entity profiles. Use whenever the answer comes from search_web / search_web_deep / fetch_url and is written in chat rather than to a file.
license: MIT
---

# Web answer format

The search already works. This is about the *shape of the answer*: sections that match the
question, an answer first, dates on anything time-sensitive, and a source next to each fact.

For a written-to-file research report, use `web-research-report` instead.

## 1. The procedure — do these in order, one tool call at a time

**Step 1.** If the question says today / latest / current / this week: call `get_datetime`.

**Step 2.** Name the sections. Write one line, before any search:
`Sections: <A>, <B>, <C>` — 2 to 4 of them, taken from the question itself, never from what a
search happened to return.

**Step 3.** Call `search_web_deep` **once**, passing those same names as `sections`. One call
returns more candidate sources — several read in full, the rest as snippets — enough material
for every section. Do not make one call per section: it is slower, it gets your SearXNG
instance rate-limited, and it buys no coverage this doesn't already give you.

**Step 4.** File the sources yourself, then write the answer in the shape of §2. The results
are not pre-sorted and are not meant to be: you know that a Tokyo flood belongs under
Asia-Pacific and that a licence note is not a speed benchmark. If nothing in the results fits
a section, say so in that section — never move another section's source into it.

Worked examples — the same call shape for any topic:

```
get_datetime()
Sections: Middle East, Europe, Asia-Pacific
search_web_deep("international news today",
                sections=["Middle East", "Europe", "Asia-Pacific"])

Sections: speed, quality, licence
search_web_deep("best GGUF models local inference",
                sections=["speed", "quality", "licence"])
```

Need one section's detail the snippets don't cover? Open that source with `fetch_url`, which
costs no new search, before spending another `search_web_deep`.

More section patterns: "X vs Y" → one section per criterion the user named, then a verdict;
"how do I fix \<error>" → cause, fix, check; "is \<library> still maintained" → status, recent
activity, alternatives.

Keep queries short and natural (3–6 words), and 2–4 sections. Budget: the loop stops you after
**6** deep searches in a turn, which one sectioned call barely dents — spend the rest on
sections the feeds missed, not on re-querying the same angle. An empty section stays in the
answer, marked empty; never silently drop the user's sub-question, and never keep querying into
the void (four thin searches in a row also stops you).

## 2. Universal shape

```
<1–3 sentences answering the question directly — the whole point, no preamble>

## <Section 1>
- **<Item>** — what it is, in one or two sentences. <date> [Source: <URL>]
- **<Item>** — … [Source: <URL>]

## <Section 2>
…

Coverage: <what you could not confirm, or which section is thin>
```

Rules that apply to every answer:

- **Answer in the user's language.** These instructions are written in English; the answer is
  not. Translate the section headings and the `Coverage:` label too — a French answer ending on
  an English label reads like a leaked template, because it is one.

- **Answer first.** The first lines answer the question. Never open with "I searched for…".
- **A section per thing asked.** Never one flat list when the user asked about several topics.
- **3–6 items per section.** Most important first. Merge duplicates from different outlets.
  A count to aim for, never a quota to fill: two real items beat six with four invented.
- **Dates.** Every time-sensitive item carries its publication date, copied **in the form the
  source gives it** (`search_web_deep` annotates it). Reformatting "2026-07-13" into
  "Jul 13, 2026" makes the grounding check flag a date that was in fact sourced, and costs the
  turn an extra generation. No date found → write "date not stated" rather than implying it is
  fresh.
- **One source per item**, inline: `[Source: <URL>]`, the real URL from the tool result.
- **Kill the filler.** No "in conclusion", no restating the question, no explaining that news
  changes fast. The last line is the coverage note, nothing else.
- **A correction is a rewrite, not a changelog.** If you are asked to re-check or fix something,
  reply with the whole answer in this shape again. Opening with "the two items are genuinely
  different" or "I have corrected the categorisation" reads as process, not news — the reader
  never saw the draft you are correcting.
- **Terminal formatting.** Headings + bullets. Tables only up to 3–4 narrow columns; beyond
  that use bullets, a wide table wraps into noise in a terminal.

## 3. Templates by question type

**News / "what happened"** — group by region (Europe, Middle East, Asia, Americas, Africa) or
by theme (conflicts, economy, politics, tech) — whichever splits the material more evenly. 3–5
items per group, each: bold headline, one line of what happened, the date, the source. Open
with a 2–3 sentence top-line of the day's dominant story.

**Comparison** — one `##` section per criterion the user named (price, performance, licence…),
each stating which side wins and why, then a final `## Verdict` of 2–3 lines with a
recommendation tied to the user's stated use case. A small table only when the criteria are
short values.

**How-to / troubleshooting** — `## Cause` (what actually produces this), `## Fix` (numbered
commands or steps, exactly as they must be typed), `## Verify` (how to know it worked).
Always state the version/OS the fix applies to, and flag when sources disagree.

**Price / specs / release** — a compact table of the values, an `as of <date>` line under it,
then a short note on what varies (region, vendor, tier). Never present one vendor's price as
the market price.

**Person / company / project** — `## What it is` (2 lines), `## Key facts` (bullets, dated),
`## Recent activity` (dated, newest first), and where relevant `## Caveats`. Mark clearly if
you found two entities with the same name.

**Definition / concept** — a plain 2–3 sentence answer, then `## How it works`, then
`## Why it matters` or `## Trade-offs`. Sources only where a specific claim needs one.

## 4. Before sending

- Does each section the user asked for exist, even if thin?
- Is the first sentence the actual answer?
- Does every time-sensitive fact carry a date, and every specific fact a source?
- Is there a coverage line saying what is missing or unconfirmed?
