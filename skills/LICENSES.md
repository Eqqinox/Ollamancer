# Licensing of the bundled skills

Agentic_1A as a whole is **MIT** licensed (see [`../LICENSE`](../LICENSE)).

Twelve of the fourteen bundled skills were written for this project and are covered by that
MIT license. **Two are adapted from third-party Apache-2.0 work and remain Apache-2.0.**

## Apache-2.0 (adapted from `anthropics/skills`)

| Skill | Upstream |
|---|---|
| [`skill-creator/`](./skill-creator/SKILL.md) | [anthropics/skills](https://github.com/anthropics/skills) — `skill-creator` |
| [`mcp-builder/`](./mcp-builder/SKILL.md) | [anthropics/skills](https://github.com/anthropics/skills) — `mcp-builder` |

Both were **modified** for this agent: rewritten to target Agentic_1A's own tools, its
`~/.agentic_1a_skills/` and `<project>/.agentic/skills/` discovery paths, and its
`~/.agentic_1a_mcp.json` MCP configuration. Each file declares `license: Apache-2.0` in its
YAML frontmatter and credits the upstream project inline.

Licensed under the Apache License, Version 2.0. You may obtain a copy of the license at
<http://www.apache.org/licenses/LICENSE-2.0>.

Unless required by applicable law or agreed to in writing, software distributed under the
License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language governing permissions
and limitations under the License.

## MIT (original to this project)

`changelog-from-git`, `commit-message`, `debug-error`, `dependency-audit`,
`dockerize-project`, `explain-codebase`, `new-python-project`, `optimize-performance`,
`security-review`, `test-and-fix`, `web-research-report`, `write-tests-for`.

## Skills you add yourself

Skills you drop into `~/.agentic_1a_skills/` or `<project>/.agentic/skills/` are yours and
are not covered by either license — nothing in this repository claims them.
