---
name: web-research-report
description: Research a topic on the web and write a well-sourced Markdown report with inline citations. Use when the user asks to research, investigate, compare, or "write a report/brief on" something current.
license: MIT
---

# Web research report

Produce a grounded report where every claim traces to a real source. No fabrication.

## Steps

1. **Anchor the date.** If the topic is time-sensitive ("latest", "current", "2026"), call
   `get_datetime` first and use the real date in queries.
2. **Search several angles, not one.** Use `search_web_deep` (reads full pages, returns dated
   sources) for the core questions, and run a *separate* search per distinct sub-topic,
   perspective, or category the user asked for. Keep queries short and natural.
3. **Read, don't skim.** For key claims, rely on `search_web_deep`'s fetched content or
   `fetch_url` the specific source. Prefer primary/dated sources; note publication dates.
4. **Extract only what's actually there.** If a search returns thin/empty/off-topic results,
   say so plainly — do not invent figures, quotes, or headlines to fill gaps.
5. **Write the report** to a Markdown file with `write_file` (chunk with `append_file` if it's
   long): a short summary, then sections by sub-topic, then a **Sources** list. Put an inline
   `[Source: <URL>]` next to each specific fact, using the real URL from the tool result.
6. **Be honest about gaps.** Clearly mark anything you couldn't verify, and distinguish sourced
   facts from your own synthesis.

## Notes

- Numbers, dates, URLs, and quoted names in the report must come from a tool result — the agent
  checks this and will nudge you if they don't.
- Requires SearXNG (or the DuckDuckGo MCP failover) to be reachable.
