---
name: serper-web-search
description: USE FOR current Google-backed web research via Serper.dev. Returns ranked web results, answer boxes, and source links.
metadata: {"openclaw":{"requires":{"bins":["python3"],"env":["SERPER_API_KEY"]},"primaryEnv":"SERPER_API_KEY"}}
---

# Serper Web Search

Use this skill to search the web via Serper.dev and retrieve ranked results.

## Commands

Standard web search:

```bash
python3 {baseDir}/scripts/serper_web_search.py "QUERY" --num 5
```

Links only:

```bash
python3 {baseDir}/scripts/serper_web_search.py "QUERY" --num 5 --links-only --limit 5
```

Raw JSON:

```bash
python3 {baseDir}/scripts/serper_web_search.py "QUERY" --num 5 --json
```

## Important

- This skill only performs search and returns result links/snippets.
- Run the command directly as shown above.
- Do not wrap it with `cd`, shell pipes, `python -c`, here-docs, or output redirection tricks.
- Use `--gl` and `--hl` when you need country or language bias.
- If you need page contents, fetch the returned URLs separately after searching.
