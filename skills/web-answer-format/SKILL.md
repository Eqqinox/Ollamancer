---
name: web-answer-format
description: Shape a web-search answer into organised sections that match what was asked — news briefings, comparisons, how-tos, prices/specs, entity profiles. Use whenever the answer comes from search_web / search_web_deep / fetch_url and is written in chat rather than to a file.
license: MIT
---

# Web answer format

Shape of the answer, not the searching. For a written-to-file report use `web-research-report`.

## Procedure

1. If the question says today / latest / current: call `get_datetime` first.
2. Decide 2–4 sections **from the question**, not from what a search returns.
3. Call `search_web_deep` **once**, passing them as `sections=[...]` — one call carries material
   for all of them. Never one call per section.
4. File the sources under your own sections and write the answer. Nothing is pre-sorted: you
   know a Tokyo flood is Asia-Pacific and a licence note is not a speed benchmark.

```
get_datetime()
search_web_deep("international news today", sections=["Middle East", "Europe", "Asia-Pacific"])
search_web_deep("best GGUF models local inference", sections=["speed", "quality", "licence"])
```

## Shape

The example is a shape to fill, not a length to match — a small model that copies it literally
ships one section with one item and answers nothing:

```
<1–3 sentences answering the question directly — no preamble>

## <Section 1>
- **<Item>** — one or two sentences. <date> [Source: <URL>]
- **<Item>** — one or two sentences. <date> [Source: <URL>]

## <Section 2>
- **<Item>** — one or two sentences. <date> [Source: <URL>]
- **<Item>** — one or two sentences. <date> [Source: <URL>]

## <Section 3>
- **<Item>** — … same again, for every section you planned

Coverage: <what is missing or unconfirmed>
```

## Rules

- **The question's count wins.** "The 3 most significant stories" means three in total, not
  three per section. Otherwise 3–6 per section. A target, never a quota — two real items beat
  six with four invented.
- **Answer first**, in the user's language, headings and the `Coverage:` label included.
- **Dates** on time-sensitive items, copied in the form the source gives them; reformatting a
  sourced date makes the grounding check flag it. None found → "date not stated".
- **One source per item**, inline `[Source: <URL>]`, real URLs only.
- **An empty section stays**, marked empty. Never move another section's source into it, never
  drop the heading.
- **A correction is a rewrite**, not a changelog — no "I have corrected the categorisation".
- Headings and bullets; tables only up to 3–4 narrow columns. No filler, no restating the
  question. The coverage line is the last line.

Need detail the snippets lack? `fetch_url` that source — it costs no new search.
