import os, tempfile, pathlib
import agent

d = pathlib.Path(tempfile.mkdtemp())
os.chdir(d)
agent.PROJECT_ROOT = d.resolve()
(d / "src").mkdir()
(d / "src" / "game.py").write_text("print(1)\n")
(d / "README.md").write_text("hi\n")
(d / "utils.py").write_text("x=1\n")

# 1. read_file with a misspelled basename → hint points at the real file
r = agent.read_file("src/gaem.py")
assert r.startswith("File not found:"), r
assert "game.py" in r and "Did you mean" in r, r

# 2. edit_file with a typo path → hint
r = agent.edit_file("READNE.md", "hi", "bye")
assert r.startswith("File not found:"), r
assert "README.md" in r, r

# 3. lint_file with a typo → hint
r = agent.lint_file("utisl.py")
assert r.startswith("File not found:"), r
assert "utils.py" in r, r

# 4. Existing file: no hint, normal behavior
r = agent.read_file("utils.py")
assert "Did you mean" not in r and "x=1" in r, r

# 5. Totally unrelated garbage name → no false suggestion
r = agent.read_file("zzzzzzzzzzqqqqq.xyz")
assert r.startswith("File not found:"), r
assert "Did you mean" not in r, r

# 6. The documented Ornith case: mistyped a path segment
(d / "mounirmeknaci_notes.txt").write_text("note\n")
r = agent.read_file("mounirekknaci_notes.txt")
assert "mounirmeknaci_notes.txt" in r, r

print("A4 ALL PASS")
