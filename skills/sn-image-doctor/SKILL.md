---
name: sn-image-doctor
description: |
  Environment diagnostic skill for SenseNova-Skills project.
  Checks that sn-image-base is properly installed and configured, validates dependencies
  and environment variables. Prompts user to configure missing required variables and saves
  them to .env file. After configuration, reloads environment and suggests agent restart if needed.
triggers:
  - "SenseNova-Skills环境检查"
  - "SenseNova-Skills doctor"
  - "sn环境检查"
  - "sn-image-doctor"
  - "environment check"
  - "health check"
  - "诊断环境"
metadata:
  project: SenseNova-Skills
  tier: 0
  category: infrastructure
  user_visible: true
---

# sn-image-doctor

## Overview

`sn-image-doctor` is an infrastructure skill (tier 0) that validates the SenseNova-Skills environment before running other skills. It ensures SenseNova-Skills project is properly installed and configured.

This skill performs comprehensive checks including:

- Installation verification of SenseNova-Skills project
- Python dependency validation
- Environment variable configuration checks, with interactive prompts to configure missing required variables and save them to `.env`
- Automatic environment reload after configuration changes, with agent restart suggestion if reload fails

## Usage

Run the doctor check to validate your environment:

```bash
# Basic check
python scripts/check_environment.py

# Verbose output with detailed diagnostics
python scripts/check_environment.py --verbose
```

## Output Format

### Text Output

```
=== SenseNova-Skills Environment Check ===

[1/3] Checking sn-image-base installation...
  ✅ Installation looks good

[2/3] Checking Python dependencies...
  ✅ Python 3.11.0
  ✅ All required packages installed

[3/3] Checking environment variables...
  ❌ SN_IMAGE_GEN_API_KEY not set (required)

  Some required environment variables are missing.
  Enter values below to save them to /path/to/.env.
  Press Enter to skip a variable.

  SN_IMAGE_GEN_API_KEY: <user input>

  ✅ Saved to /path/to/.env: SN_IMAGE_GEN_API_KEY
  🔄 Reloading environment...
  ✅ Environment reloaded successfully

=== Summary ===
✅ Environment is properly configured
```

If reload fails, the output will suggest restarting the agent:

```
  ✅ Saved to /path/to/.env: SN_IMAGE_GEN_API_KEY
  🔄 Reloading environment...
  ⚠️  Failed to reload environment: <error message>
  💡 Suggestion: Restart the agent to apply new configuration
```

### Error Output

When checks fail:

```
=== SenseNova-Skills Environment Check ===

[1/3] Checking sn-image-base installation...
  ❌ sn-image-base directory not found
  Expected location: /path/to/skills/sn-image-base

[2/3] Checking Python dependencies...
  ❌ Missing packages: httpx, pillow
  Run: pip install -r skills/sn-image-base/requirements.txt

=== Summary ===
❌ Environment check failed
Please fix the errors above before using SenseNova-Skills.
```

## Troubleshooting

### sn-image-base Not Found

**Problem:** `sn-image-base` directory not found

**Solution:**

```bash
# Ensure you're in the project root
cd /path/to/SenseNova-Skills

# Verify the directory exists
ls -la skills/sn-image-base
```

### Missing Dependencies

**Problem:** Required Python packages not installed

**Solution:**

```bash
# Install dependencies
pip install -r skills/sn-image-base/requirements.txt

# Or use a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r skills/sn-image-base/requirements.txt
```

### Missing Environment Variables

**Problem:** Required environment variables not set

**Solution:**

```bash
# Set environment variables in your shell
export SN_IMAGE_GEN_API_KEY="your-api-key"
export SN_IMAGE_GEN_BASE_URL="https://your-api-endpoint.com"

# Or create a .env file
cat > .env << EOF
SN_IMAGE_GEN_API_KEY=your-api-key
SN_IMAGE_GEN_BASE_URL=https://token.sensenova.cn/v1
SN_CHAT_API_KEY=your-chat-api-key
SN_CHAT_BASE_URL=https://token.sensenova.cn/v1
SN_CHAT_TYPE=openai-completions
SN_CHAT_MODEL=sensenova-6.7-flash-lite
EOF

# Load .env file
source .env  # Or use a tool like python-dotenv
```

### API Connectivity Issues

**Problem:** Cannot reach API endpoints

**Solution:**

1. Verify network connectivity
2. Check firewall settings
3. Verify API endpoint URLs are correct
4. Test with curl:

   ```bash
   curl -I https://your-api-endpoint.com
   ```

## Integration with Other Skills

This skill is designed to be run before using other skills in the SenseNova-Skills project:

```bash
# 1. Run doctor check
python skills/sn-image-doctor/scripts/check_environment.py

# 2. If checks pass, use other skills
python skills/sn-image-base/scripts/sn_agent_runner.py sn-image-generate \
    --prompt "A beautiful landscape"
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed diagnostic information |
| `--help` | Show help message |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed |

## See Also

- `sn-image-base/SKILL.md` - Base-layer skill documentation
- `sn-image-base/references/api_spec.md` - API specification
- `sn-infographic/SKILL.md` - Example of a skill that depends on sn-image-base
