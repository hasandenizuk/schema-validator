---
name: validate-schema
description: Validate JSON-LD structured data across HTML pages. Checks JSON syntax, schema.org vocabulary, and Google Rich Results requirements. Use when editing web pages, before deploying, or when GSC reports schema errors.
metadata:
  author: hasandenizuk
  version: "1.0.0"
  category: seo
  tags:
    - schema
    - json-ld
    - structured-data
    - google
    - rich-results
    - seo
    - validation
triggers:
  - /validate-schema
  - validate schema
  - check structured data
  - schema validation
  - rich results check
---

# Schema Validator

Validates JSON-LD structured data in HTML pages against three layers:
1. **JSON syntax** - parsing errors, bad characters (curly quotes)
2. **Schema.org vocabulary** - valid @context, @type, known types
3. **Google Rich Results** - required/recommended fields per type (Article, FAQPage, HowTo, Product, SoftwareApplication, Event, JobPosting, Recipe, Review, VideoObject, LocalBusiness, BreadcrumbList, and more)

## How to Run

The script is `validate-schema.py` in the same directory as this SKILL.md.

Find the script path relative to where you installed it. Common locations:
- `~/.agents/skills/validate-schema/validate-schema.py` (cross-platform)
- `~/.claude/skills/validate-schema/validate-schema.py` (Claude Code)
- `~/.gemini/skills/validate-schema/validate-schema.py` (Gemini CLI)
- Or wherever you cloned the repo

### Validate all pages in current project
```bash
python3 <script-path>/validate-schema.py
```
Auto-detects the HTML root (looks for pub-www/, public/, dist/, build/, out/, _site/, www/).

### Validate with explicit root
```bash
python3 <script-path>/validate-schema.py public/
```

### Validate single file
```bash
python3 <script-path>/validate-schema.py --file public/en/about.html
```

### Verbose mode (includes P2 info)
```bash
python3 <script-path>/validate-schema.py --verbose
```

### JSON output (for CI/pipelines)
```bash
python3 <script-path>/validate-schema.py --json
```

## Instructions for the AI Assistant

When this skill is invoked:

1. **Determine scope:**
   - If the user specified a file or directory, use that
   - If user just said `/validate-schema`, run against the current project's web root
   - If after editing pages, validate only the changed files

2. **Run the validator:**
   ```bash
   python3 <script-path>/validate-schema.py <path-or-flags>
   ```

3. **Interpret results:**
   - **P0 errors**: Must fix - these block Google Rich Results. Offer to fix immediately.
   - **P1 warnings**: Should fix - these limit what snippets Google shows. List them, ask if user wants fixes.
   - **P2 info**: Optional - mention only in verbose mode.

4. **For fixes**, apply changes directly to the HTML files, then re-run the validator on the changed files to confirm.

5. **Exit code**: 0 = no P0 errors, 1 = has P0 errors. Use this to gate deployments.

## Severity Model

| Level | Meaning | Example |
|-------|---------|---------|
| P0 error | Blocks rich results | Invalid JSON, missing @type, FAQPage with no mainEntity |
| P1 warning | Missing recommended field | Article missing publisher, Product missing image |
| P2 info | Non-standard or optional | Missing applicationCategory, availability |

## No Dependencies

Pure Python 3.6+, stdlib only. No pip install needed.

## About

GitHub: [hasandenizuk/schema-validator](https://github.com/hasandenizuk/schema-validator)
Author: [Hasan Deniz](https://hasandeniz.com)
