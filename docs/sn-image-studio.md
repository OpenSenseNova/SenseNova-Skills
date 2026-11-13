# Image Studio

English | [简体中文](sn-image-studio_cn.md)

[`sn-image-studio`](../skills/sn-image-studio/SKILL.md) is a local bilingual Web workbench
for browsing style cases, editing prompts, uploading input images, and generating or editing
SenseNova U1.5 images. It includes its own image client and does not require `sn-image-base`.

## Choose a workflow

| Workflow | How it runs |
| --- | --- |
| Direct generation or editing | Submit the current prompt and ordered uploads from the page; Studio calls its image client without an Agent. |
| Adapt a prompt to a requirement | A selected Codex, Claude Code, or Hermes Agent works in a separate ACP session, revises the prompt, and optionally requests image generation through Studio. |
| Publish a supplied case | Import a prompt, effect image, and case metadata into the local case library. |

The Agent's authentication and model configuration are separate from the SenseNova image
API key. Configuring a chat model alone does not provide image access. The current ACP
profiles are `codex`, `claude`, and `hermes`; OpenClaw is not a Studio ACP profile.

## Install

Use Python 3.10+ and install the complete `skills/sn-image-studio/` directory, including
`assets/`, `references/`, `scripts/`, and `requirements.txt`. It can also run directly from
this repository. The following examples use a macOS/Linux/WSL shell, starting in the
repository root; replace `SKILL_DIR` with the absolute installed skill path when needed.

```bash
export SKILL_DIR="$PWD/skills/sn-image-studio"
export STUDIO_ENV="$PWD/.env"
python3 -m venv .venv-image-studio
. .venv-image-studio/bin/activate
python -m pip install -r "$SKILL_DIR/requirements.txt"
python "$SKILL_DIR/scripts/catalog.py" validate
```

Run Studio with that same Python environment. Set the two path variables again in new
shell sessions. `STUDIO_ENV` is a shell variable used in these examples, not an automatic
configuration variable read by Studio.

## Configure image access

Use the page's configuration form or edit the selected `.env`. Missing credentials open
the form when the page loads. Keep keys in that form or the configuration file, not in chat.

Choose the endpoint for the account that issued the image key:

| Account region | Base URL | Platform documentation |
| --- | --- | --- |
| International | `https://token.sensenova.ai/v1` | [International docs](https://platform.sensenova.ai/docs) |
| Mainland China | `https://token.sensenova.cn/v1` | [Mainland China docs](https://platform.sensenova.cn/docs) |

Example image-specific settings for an international account (replace the Base URL for a
mainland China account):

```dotenv
SN_IMAGE_GEN_BASE_URL="https://token.sensenova.ai/v1"
SN_IMAGE_GEN_API_KEY="your-image-api-key"
SN_IMAGE_GEN_MODEL="sensenova-u1.5-lite"
SN_IMAGE_GEN_MODEL_TYPE="sensenova"
```

The account must have access to the chosen U1.5 model. Studio uses these fallbacks:

| Setting | Resolution order |
| --- | --- |
| API key | `SN_IMAGE_GEN_API_KEY` → `SN_API_KEY`; no built-in key |
| Base URL | `SN_IMAGE_GEN_BASE_URL` → `SN_BASE_URL` → `https://token.sensenova.cn/v1` |
| Model | `SN_IMAGE_GEN_MODEL` → `sensenova-u1.5-lite` |
| Protocol | `SN_IMAGE_GEN_MODEL_TYPE` → `sensenova` |

By default, Studio reads `.env` in the command's current directory, not automatically in
the launching Agent's home. Pass the same `--env-file` absolute path to each command.
Values in that file override same-name process variables before the fallback chain is
applied. The page saves image-specific overrides and preserves unrelated settings.

## Open the workbench

For direct image generation without an ACP Agent:

```bash
python "$SKILL_DIR/scripts/studio.py" doctor --env-file "$STUDIO_ENV"
python "$SKILL_DIR/scripts/studio.py" serve --background --language en --env-file "$STUDIO_ENV"
```

`doctor` reports missing configuration or dependencies; it does not verify provider login
or make an image request. The page can still open for configuration when a key is missing.
Without `--harness`, requirement submission is unavailable, but direct generation is available
after image configuration is complete.

For Agent-assisted prompt adaptation, first install and authenticate **one** selected ACP
server using the [ACP setup reference](../skills/sn-image-studio/references/acp.md):

| Selection | ACP server setup |
| --- | --- |
| `codex` | `npm install -g @agentclientprotocol/codex-acp@2.5.0` |
| `claude` | `npm install -g @agentclientprotocol/claude-agent-acp@0.100.0` |
| `hermes` | Install Hermes and its ACP dependencies, then verify `hermes acp --check`. |

The npm adapters also require a compatible Node.js/npm installation. Follow the selected
adapter's authentication instructions linked in the reference. Example using Hermes:

```bash
python "$SKILL_DIR/scripts/studio.py" doctor --harness hermes --env-file "$STUDIO_ENV"
python "$SKILL_DIR/scripts/studio.py" serve --background --harness hermes --language en --env-file "$STUDIO_ENV"
```

Replace `hermes` consistently with the chosen profile. If a direct-only or differently
configured Studio already uses port 4318, choose a free port with `--port 4319`, or stop
that specific instance before switching. Studio does not select or fall back to another
Agent just because it is installed.

Open the complete returned `url`, including its language query. The default address is
`http://127.0.0.1:4318/`. Use `--language zh-CN` for Chinese or `auto` for the saved/browser
preference. The page also has a language switch; each language keeps an independent prompt draft.

## Use and verify

1. Select a style case and inspect its preview, prompt, and required inputs. Sample images
   illustrate the style; they are not automatically sent as model inputs.
2. Upload the required images in order and check their roles. No inputs means text-to-image;
   uploaded inputs use image editing.
3. Edit the prompt directly, or submit a requirement such as "Keep the paper-cut style,
   change the scene to Guilin, and preserve the title exactly." Choose whether to generate
   after the Agent's rewrite.
4. Check the task result and image preview. A successful rewrite alone is not a successful
   image task. Newer manual prompt edits are retained; a stale rewrite becomes a candidate.

The default resolution is 2K. This client's 4K option is limited to `sensenova-u1.5-lite`;
editing uses `size=auto`. See the [image API reference](../skills/sn-image-studio/references/image-api.md).
Adapting a case does not guarantee the same visual result as its preview.

Tasks run in the backend, so closing the page or launching conversation does not stop them.
Reopening the page restores result display. A service restart is different: unfinished tasks
are marked failed with an uncertainty notice and paid requests are not automatically replayed.
For an unknown result or timeout, inspect the original task before submitting again.

Runtime files default to `~/.cache/sn-image-studio/<port>/`; use `--data-dir` to change that
location. Foreground mode (omit `--background`) can be stopped with Ctrl+C. For background
mode, record the returned `pid` and stop only that process when no task is active; closing
the browser does not stop the service.

To publish a supplied prompt and effect image, follow the
[case-authoring guide](../skills/sn-image-studio/references/case-authoring.md), use
`catalog.py add`, then run `catalog.py validate`. Preserve the original prompt and public
attribution; keep private source links and internal notes out of the published catalog.
