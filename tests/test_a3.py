import agent

print("trafilatura installed:", agent.trafilatura is not None)

# A real-looking UTF-8 article whose text contains a typographic apostrophe (’ = U+2019,
# bytes E2 80 99 in UTF-8). This is the exact character that showed up as "â€™" when
# requests decoded the page as latin-1/cp1252 via r.text (section 7 quater).
article_text = ("Apple’s newest product line was unveiled today. "
                "The company’s engineers said it’s the biggest change in years, "
                "and analysts’ reactions were broadly positive across markets. " * 3)
html = ("<html><head><meta charset='utf-8'><title>News</title></head>"
        f"<body><article><h1>Report</h1><p>{article_text}</p></article></body></html>")
html_bytes = html.encode("utf-8")

# 1. BYTES path (the fix): apostrophe survives, no mojibake
text_fixed, _ = agent._extract_with_meta(html_bytes, "http://ex.com/a", "ISO-8859-1")
assert "’" in text_fixed, repr(text_fixed[:200])
assert "â€™" not in text_fixed, "mojibake present in bytes path!"
assert "Apple" in text_fixed

# 2. STR path with the WRONG decode (simulates old r.text guessing cp1252) → mojibake,
#    and crucially the correct apostrophe is NOT recoverable. Proves bytes path differs.
mojibake_str = html_bytes.decode("cp1252")
text_broken, _ = agent._extract_with_meta(mojibake_str, "http://ex.com/a")
assert "â€™" in text_broken, repr(text_broken[:200])
assert "’" not in text_broken, "broken path should not contain the clean char"

# 3. Regex fallback (short text → trafilatura returns nothing) decodes bytes with the hint.
#    cp1252 byte 0x92 is a right single quote; utf-8 would mis-decode it.
snippet = "<p>Ol\x92 timers</p>".encode("cp1252") if False else b"<p>caf\xe9 open</p>"
txt, _ = agent._extract_with_meta(snippet, "", "cp1252")  # 0xE9 = é in cp1252/latin-1
assert "café" in txt, repr(txt)

# 4. Bad/unknown encoding hint must not crash (falls back to utf-8 replace)
txt2, _ = agent._extract_with_meta(b"<p>hello world here</p>", "", "not-a-real-charset")
assert "hello world" in txt2, txt2

# 5. Plain str still works (back-compat)
txt3, _ = agent._extract_with_meta("<p>plain string path works fine</p>", "")
assert "plain string" in txt3

print("A3 ALL PASS")
