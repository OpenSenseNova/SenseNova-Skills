import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const skillPath = new URL("../skills/sn-deep-research/SKILL.md", import.meta.url);
const agentsDir = new URL("../skills/sn-deep-research/agents/", import.meta.url);

function read(path) {
  return readFileSync(path, "utf8");
}

test("every deep-research role dispatch carries the request language", () => {
  const skill = read(skillPath);
  const dispatchBlocks = [...skill.matchAll(/```text\n([\s\S]*?)```/g)]
    .map((match) => match[1])
    .filter((block) => block.startsWith("先读取 {plugin_role_dir}/"));

  assert.equal(dispatchBlocks.length, 10, "expected all ten role dispatch templates");
  for (const block of dispatchBlocks) {
    const role = block.match(/^先读取 \{plugin_role_dir\}\/([^ ]+)/)?.[1] ?? "unknown";
    assert.match(block, /^原始需求:\{query\}$/m, `${role} is missing the original query`);
    assert.match(block, /^language:\{language\}$/m, `${role} is missing the language anchor`);
  }
});

test("every deep-research agent consumes the language anchor", () => {
  const agentFiles = readdirSync(agentsDir)
    .filter((name) => name.endsWith(".md"))
    .sort();

  assert.equal(agentFiles.length, 9, "expected all deep-research agent contracts");
  for (const name of agentFiles) {
    const content = read(join(agentsDir.pathname, name));
    assert.match(content, /`language`|language=\{language\}/, `${name} does not consume language`);
  }
});

test("outline validation binds style language to the request", () => {
  const files = [
    skillPath,
    new URL("../skills/sn-deep-research/agents/report-planner.md", import.meta.url),
  ];

  for (const path of files) {
    const content = read(path);
    const commands = [...content.matchAll(/python3 .*?validate_outline\.py \\\n([\s\S]*?)```/g)];
    assert.ok(commands.length > 0, `${path.pathname} has no outline validation command`);
    for (const command of commands) {
      assert.match(command[0], /--language \{language\}/, `${path.pathname} omits --language`);
    }
  }
});
