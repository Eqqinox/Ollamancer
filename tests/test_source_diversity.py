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

print("source diversity: ALL PASS")
