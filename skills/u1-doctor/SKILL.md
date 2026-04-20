---
name: u1-doctor
description: |
  Environment diagnostic skill for SenseNova-Skills project.
  Checks that u1-image-base is properly installed and configured, validates dependencies
  and environment variables. Prompts user to configure missing required variables and saves
  them to .env file. After configuration, reloads environment and suggests agent restart if needed.
triggers:
  - "SenseNova-Skills环境检查"
  - "SenseNova-Skills doctor"
  - "u1环境检查"
  - "u1-doctor"
  - "environment check"
  - "health check"
  - "诊断环境"
metadata:
  project: SenseNova-Skills
  tier: 0
  category: infrastructure
  user_visible: true
---

# u1-doctor

## Overview

`u1-doctor` is an infrastructure skill (tier 0) that validates the SenseNova-Skills environment before running other skills. It ensures SenseNova-Skills project is properly installed and configured.

This skill performs comprehensive checks including:

- Installation verification of SenseNova-Skills project
- Python dependency validation
- Environment variable configuration checks, with interactive prompts to configure missing required variables and save them to `.env`
- Automatic environment reload after configuration changes, with agent restart suggestion if reload fails

## Usage

Run the doctor check to validate your environment:

```bash
# Basic check
python u1_doctor/check_environment.py

# Verbose output with detailed diagnostics
python u1_doctor/check_environment.py --verbose
```

## Output Format

### Text Output

```
=== SenseNova-Skills Environment Check ===

[1/3] Checking u1-image-base installation...
  ✅ Installation looks good

[2/3] Checking Python dependencies...
  ✅ Python 3.11.0
  ✅ All required packages installed

[3/3] Checking environment variables...
  ❌ U1_API_KEY not set (required)

  Some required environment variables are missing.
  Enter values below to save them to /path/to/.env.
  Press Enter to skip a variable.

  U1_API_KEY: <user input>

  ✅ Saved to /path/to/.env: U1_API_KEY
  🔄 Reloading environment...
  ✅ Environment reloaded successfully

=== Summary ===
✅ Environment is properly configured
```

If reload fails, the output will suggest restarting the agent:

```
  ✅ Saved to /path/to/.env: U1_API_KEY
  🔄 Reloading environment...
  ⚠️  Failed to reload environment: <error message>
  💡 Suggestion: Restart the agent to apply new configuration
```

### Error Output

When checks fail:

```
=== SenseNova-Skills Environment Check ===

[1/3] Checking u1-image-base installation...
  ❌ u1-image-base directory not found
  Expected location: /path/to/skills/u1-image-base

[2/3] Checking Python dependencies...
  ❌ Missing packages: httpx, pillow
  Run: pip install -r skills/u1-image-base/requirements.txt

=== Summary ===
❌ Environment check failed
Please fix the errors above before using SenseNova-Skills.
```

## Troubleshooting

### u1-image-base Not Found

**Problem:** `u1-image-base` directory not found

**Solution:**

```bash
# Ensure you're in the project root
cd /path/to/SenseNova-Skills

# Verify the directory exists
ls -la skills/u1-image-base
```

### Missing Dependencies

**Problem:** Required Python packages not installed

**Solution:**

```bash
# Install dependencies
pip install -r skills/u1-image-base/requirements.txt

# Or use a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r skills/u1-image-base/requirements.txt
```

### Missing Environment Variables

**Problem:** Required environment variables not set

**Solution:**

```bash
# Set environment variables in your shell
export U1_API_KEY="your-api-key"
export U1_IMAGE_GEN_BASE_URL="https://your-api-endpoint.com"

# Or create a .env file
cat > .env << EOF
U1_API_KEY=your-api-key
U1_IMAGE_GEN_BASE_URL=https://your-api-endpoint.com
VLM_BASE_URL=http://127.0.0.1:615
VLM_MODEL=sensenova-122b
LLM_BASE_URL=http://127.0.0.1:615
LLM_MODEL=sensenova-122b
U1_LM_API_KEY=your-lm-api-key
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
python skills/u1-doctor/u1_doctor/check_environment.py

# 2. If checks pass, use other skills
python skills/u1-image-base/u1_image_base/openclaw_runner.py u1-image-generate \
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

- `u1-image-base/SKILL.md` - Base-layer skill documentation
- `u1-image-base/reference/api_spec.md` - API specification
- `u1-infographic/SKILL.md` - Example of a skill that depends on u1-image-base
