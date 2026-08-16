"""search_web_deep must spread its reads across outlets, not stack one source.

Relevance order alone can hand back six articles from a single wire service. Reading six
pages from one outlet gives the user nothing they could not get by visiting that outlet
themselves — the point of a deep read is the cross-source picture. This is enforced in code
rather than asked for in the prompt, the same way news-category routing and the forced-search
prefix are.
"""
import agent  # noqa: F401  (import side effects: package wiring)
from urllib.parse import urlparse

from agentic import config
from agentic.tools.web import _diversify_by_domain

def _r(*urls):
    return [{"url": u, "title": u, "content": "x"} for u in urls]

def _hosts(picked):
    return [urlparse(r["url"]).netloc.replace("www.", "") for r in picked]

# 1. a diverse pool yields distinct outlets first, in relevance order
pool = _r("https://apnews.com/a", "https://apnews.com/b", "https://apnews.com/c",
          "https://www.bbc.co.uk/x", "https://www.theguardian.com/y",
          "https://www.npr.org/z", "https://www.reuters.com/w")
got = _hosts(_diversify_by_domain(pool, 4))
assert len(set(got)) == 4, got
assert got[0] == "apnews.com", got            # most relevant is still read first
assert got == ["apnews.com", "bbc.co.uk", "theguardian.com", "npr.org"], got

# 2. the budget is still fully used when there are too few distinct domains
pool2 = _r("https://apnews.com/a", "https://apnews.com/b",
           "https://www.bbc.co.uk/x", "https://www.bbc.co.uk/y")
got2 = _diversify_by_domain(pool2, 4)
assert len(got2) == 4, got2                   # never returns fewer pages than asked for
assert _hosts(got2)[:2] == ["apnews.com", "bbc.co.uk"], _hosts(got2)

# 3. a single-source pool degrades gracefully rather than returning nothing
pool3 = _r(*[f"https://apnews.com/{i}" for i in range(6)])
assert len(_diversify_by_domain(pool3, 6)) == 6

# 4. www. and bare host count as the same outlet
pool4 = _r("https://www.bbc.co.uk/a", "https://bbc.co.uk/b", "https://www.npr.org/c")
assert _hosts(_diversify_by_domain(pool4, 2)) == ["bbc.co.uk", "npr.org"]

# 5. never returns more than asked
assert len(_diversify_by_domain(pool, 3)) == 3

# ── Section fan-out: per-section coverage without per-section requests ───────
# The model plans "Sections: A, B, C" and used to need one search per section, which it never
# did (seven live runs) and which would have tripled what upstream engines see. Sections are
# matched against the RSS pool instead: fetched once, filtered N times, zero extra requests.
import time
from agentic import state
from agentic.tools import web

_POOL = [
    {"source": "BBC", "title": "Strike hits Gulf shipping lane",
     "url": "https://bbc.co.uk/1", "summary": "Middle East tensions", "published": "Sat, 15 Aug 2026"},
    {"source": "Guardian", "title": "Wildfire on the Croatian coast",
     "url": "https://theguardian.com/2", "summary": "Europe heatwave", "published": "Sat, 15 Aug 2026"},
    {"source": "NPR", "title": "Earthquake strikes Indonesia",
     "url": "https://npr.org/3", "summary": "Asia quake damage", "published": "Sat, 15 Aug 2026"},
]

# 6. each section gets only its own items
assert [i["url"] for i in web._match_rss(_POOL, "Europe")] == ["https://theguardian.com/2"]
assert [i["url"] for i in web._match_rss(_POOL, "Indonesia")] == ["https://npr.org/3"]

# 7. exclude_urls prevents the same item being handed back twice across calls
claimed = set()
first = web._match_rss(_POOL, "Middle East", exclude_urls=claimed)
second = web._match_rss(_POOL, "shipping", exclude_urls=claimed)
assert [i["url"] for i in first] == ["https://bbc.co.uk/1"]
assert second == [], second

# 8. no match returns empty rather than the nearest thing
assert web._match_rss(_POOL, "Antarctica") == []

# 8b. breadth scales with the number of sections and stays bounded
assert web._breadth_cap([]) == config.SECTION_RSS_ITEMS
assert web._breadth_cap(["a", "b", "c"]) == 3 * config.SECTION_RSS_ITEMS
assert web._breadth_cap(["a"] * 20) <= 12

# 8c. freshness filter for news. Handing back the results the search already had was free
# breadth everywhere else, but SearXNG's news category answered "international news today" with
# Reuters pieces from 2023 and an undated 2025 page, and the model wrote them up as today's
# news. Old goes; undated goes too, being indistinguishable from old for a "today" question.
import datetime as _dt
_now = _dt.datetime.now(_dt.timezone.utc)
_news = [
    {"url": "https://a/1", "publishedDate": (_now - _dt.timedelta(days=900)).isoformat()},
    {"url": "https://a/2", "publishedDate": (_now - _dt.timedelta(days=1)).isoformat()},
    {"url": "https://a/3"},                                   # undated
    {"url": "https://a/4", "publishedDate": (_now - _dt.timedelta(days=3)).isoformat()},
    {"url": "https://a/5", "publishedDate": "not a date"},     # unparseable, not a crash
]
kept = [r["url"] for r in web._freshness_filter(_news)]
assert kept == ["https://a/2", "https://a/4"], kept        # newest first, stale/undated dropped
# nothing fresh at all is a real state (that whole live result set was stale): return empty and
# let the caller decide, rather than silently keeping the stale ones
assert web._freshness_filter([_news[0], _news[2]]) == []

# 9. the pool is fetched once and reused: N sections cost no extra requests
calls = {"n": 0}
class _FakeResp:
    content = b"<rss/>"
def _counting_get(url, **kw):
    calls["n"] += 1
    return _FakeResp()
_real_get, _real_parser = web.requests.get, web.feedparser
web.requests.get = _counting_get
web.feedparser = type("_P", (), {"parse": staticmethod(lambda c: type("_F", (), {"entries": []})())})
state._rss_cache.clear()
config.RSS_ENABLED = "on"
web._rss_pool()
after_first = calls["n"]
web._rss_pool(); web._rss_pool()          # two more "sections"
assert calls["n"] == after_first, f"pool refetched: {calls['n']} vs {after_first}"
assert after_first == len(config.NEWS_RSS_FEEDS), after_first

# the cache is TTL-bound, not permanent
state._rss_cache["pool"] = (time.time() - config.SEARCH_CACHE_TTL - 1, [])
web._rss_pool()
assert calls["n"] > after_first, "an expired pool must be refetched"
web.requests.get, web.feedparser = _real_get, _real_parser
state._rss_cache.clear()

# 10. word boundaries and best-tier scoring still guard *query* matching, which is what RSS
# matching is for. Deciding which section an item belongs to is no longer done here at all:
# three live runs produced three different mis-filings, and the model — which knows Japan is in
# Asia — fixed one of them unprompted. Code supplies breadth; the model files.
_TRAP = [
    {"source": "AJ", "title": "Quake hits Southeast Asia", "url": "https://aj.com/q",
     "summary": "Indonesia damage", "published": "Sun, 16 Aug 2026"},
    {"source": "BBC", "title": "Talks resume in the Middle East", "url": "https://bbc.co.uk/t",
     "summary": "Gulf diplomacy", "published": "Sun, 16 Aug 2026"},
]
assert [i["url"] for i in web._match_rss(_TRAP, "Middle East")] == ["https://bbc.co.uk/t"]
assert [i["url"] for i in web._match_rss(_TRAP, "Asia-Pacific")] == ["https://aj.com/q"]

# best tier only: the third live mis-file was a Japan story landing in "Middle East" because
# its summary says "east of Tokyo". A full two-term match exists, so the one-term match is out.
_TIER = [
    {"source": "X", "title": "Rain kills five in Japan", "url": "https://x.com/1",
     "summary": "Chiba prefecture, east of Tokyo", "published": ""},
    {"source": "Y", "title": "Middle East summit opens", "url": "https://y.com/2",
     "summary": "regional talks", "published": ""},
]
assert [i["url"] for i in web._match_rss(_TIER, "Middle East")] == ["https://y.com/2"]
# but when no item matches in full, the partial match still fills the section rather than
# leaving it empty (the Asia-Pacific case)
assert [i["url"] for i in web._match_rss(_TIER, "Asia-Pacific Japan")] == ["https://x.com/1"]

# 11. the model's own plan line is routed into the search call, because it writes the line
# reliably and omits the argument just as reliably
from agentic import loop
msgs = [{"role": "assistant", "content": "Sections: Europe, Middle East, Asia-Pacific",
         "tool_calls": [{}]}]
out = loop._route_planned_sections("search_web_deep", {"query": "news today"}, msgs)
assert out["sections"] == ["Europe", "Middle East", "Asia-Pacific"], out
# an explicit argument always wins over the routed one
explicit = loop._route_planned_sections(
    "search_web_deep", {"query": "x", "sections": ["Only Mine"]}, msgs)
assert explicit["sections"] == ["Only Mine"]
# a single named section is the query again, not a plan
one = loop._route_planned_sections(
    "search_web_deep", {"query": "x"}, [{"role": "assistant", "content": "Sections: Europe"}])
assert "sections" not in one, one
# other tools are untouched
assert loop._route_planned_sections("search_web", {"query": "x"}, msgs) == {"query": "x"}
# and no plan line means no invention
assert "sections" not in loop._route_planned_sections(
    "search_web_deep", {"query": "x"}, [{"role": "assistant", "content": "no plan here"}])

print("source diversity: ALL PASS")
