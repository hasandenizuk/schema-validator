# Schema Validator

A zero-dependency Python CLI tool that validates JSON-LD structured data in HTML pages against Google Rich Results requirements.

Run it on any static site, CMS output, or build directory to catch schema errors before Google does.

## Why This Exists

Google Search Console reports structured data errors days or weeks after crawling. By then, your pages have been live with broken or incomplete schema markup, missing rich results opportunities.

There is no public Google Rich Results Test API. The web tool only tests one URL at a time. No batch validation exists.

This tool fills that gap: validate hundreds of pages locally, in seconds, before you deploy.

## What It Checks

Three validation layers, each building on the last:

| Layer | What | Examples |
|-------|------|---------|
| **1. JSON Syntax** | Valid JSON, encoding issues | Parse errors, curly quotes that break JSON |
| **2. Schema.org Vocabulary** | Correct `@context`, valid `@type` values | Misspelled types, missing `@type`, unknown vocabulary |
| **3. Google Rich Results** | Required and recommended fields per type | FAQPage without questions, Article missing author, Product without brand |

### Supported Schema Types

Full Google-rules coverage for:

- **Article / NewsArticle / BlogPosting** - headline, datePublished, author, image, publisher
- **FAQPage** - mainEntity with Question/Answer pairs
- **HowTo** - name, steps, sections
- **Product** - name, brand, image, offers (price, shipping, return policy)
- **SoftwareApplication** - name, offers, applicationCategory
- **Event** - name, startDate, location, endDate
- **JobPosting** - title, description, datePosted, hiringOrganization
- **Recipe** - name, image, ingredients, instructions
- **Review** - reviewRating, author, itemReviewed
- **VideoObject** - name, description, thumbnailUrl, uploadDate
- **LocalBusiness** - name, address, telephone
- **BreadcrumbList** - itemListElement with position and name
- **Organization / WebSite / WebPage** - identity and site structure fields
- **Course / Dataset** - required educational/data fields

Plus smart handling of:
- `OfferCatalog` with nested offers
- `@id` references (skips validation, Google follows refs to definitions)
- `HowToSection` with nested `HowToStep` items

## Severity Model

| Level | Label | Meaning | Example |
|-------|-------|---------|---------|
| P0 | ERROR | Blocks rich results entirely | Invalid JSON, FAQPage with no mainEntity |
| P1 | WARNING | Missing recommended field, limits what Google shows | Product missing brand, Article missing image |
| P2 | INFO | Optional, non-standard usage | Missing applicationCategory |

Exit code `1` when P0 errors exist. Use this to gate deployments in CI.

## Installation

No installation needed. Download the script and run it with Python 3.6+.

```bash
# Clone
git clone https://github.com/hasandenizuk/schema-validator.git
cd schema-validator

# Or just download the script
curl -O https://raw.githubusercontent.com/hasandenizuk/schema-validator/main/validate-schema.py
```

**Requirements:** Python 3.6+ (stdlib only, no pip install needed)

## Usage

### Validate all HTML pages in a directory

```bash
python3 validate-schema.py public/
python3 validate-schema.py dist/
python3 validate-schema.py _site/
```

### Auto-detect the HTML root

```bash
# Looks for pub-www/, public/, dist/, build/, out/, _site/, www/
python3 validate-schema.py
```

### Validate a single file

```bash
python3 validate-schema.py --file public/en/about.html
```

### Verbose mode (includes P2 info-level findings)

```bash
python3 validate-schema.py public/ --verbose
```

### JSON output (for CI pipelines and tooling)

```bash
python3 validate-schema.py public/ --json
```

## Example Output

```
P0 ko/pricing.html
  ERROR: JSON parse error: Expecting ',' delimiter: line 548 column 25
  
P0 ja/pricing.html  
  ERROR: Unknown @type 'FAQページ' - not in schema.org vocabulary

P1 en/blog/my-article.html
  WARN:  Article: missing required 'author' [author]
  WARN:  Article: missing recommended 'image' [image]

P1 de/about.html
  WARN:  Event: missing recommended 'endDate' [endDate]

============================================================
SUMMARY: 173 files scanned
  OK  169 clean
  P0  2 errors (blocks rich results)
  P1  2 warnings (limits snippets)
```

## Use Cases

### 1. Pre-deploy validation for static sites

Run before every deployment to catch schema issues that would otherwise only surface in GSC days later.

```bash
# In your deploy script or CI
python3 validate-schema.py dist/
if [ $? -ne 0 ]; then
  echo "Schema errors found. Fix before deploying."
  exit 1
fi
```

### 2. Multilingual site maintenance

Sites with 10+ language versions often have schema errors introduced during translation: translated `@type` values, curly quotes in JSON strings, missing fields in copied templates.

```bash
# Check all languages at once
python3 validate-schema.py public/ --verbose
```

### 3. After bulk content updates

When updating schema markup across many pages (adding shipping details, return policies, new FAQ entries), validate the entire site in one command.

```bash
python3 validate-schema.py public/
# 0 errors? Safe to deploy.
```

### 4. CI/CD pipeline integration

Add to GitHub Actions, GitLab CI, or any pipeline:

```yaml
# .github/workflows/schema-check.yml
name: Schema Validation
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python3 validate-schema.py dist/
```

### 5. SEO audits

Generate a JSON report for analysis or integration with other SEO tools:

```bash
python3 validate-schema.py public/ --json > schema-report.json
```

### 6. Claude Code skill (for Claude Code users)

Drop the script into your tools directory and create a skill to invoke it from any project:

```bash
/validate-schema          # validates current project
/validate-schema --verbose  # with P2 info
```

## How It Compares

| Tool | JSON Syntax | Schema.org Vocab | Google Rules | Batch | Offline | Free |
|------|:-----------:|:----------------:|:------------:|:-----:|:-------:|:----:|
| **This tool** | Yes | Yes | Yes | Yes | Yes | Yes |
| Google Rich Results Test | Yes | Yes | Yes | No (1 URL) | No | Yes |
| Schema Markup Validator | Yes | Yes | Partial | No (1 URL) | No | Yes |
| Screaming Frog | No | Partial | Via GSC API | Yes | No | Paid |
| structured-data-testing-tool (npm) | Yes | Partial | Presets | Yes | Yes | Yes |

Key differences:
- **No API dependency** - works offline, no rate limits, no account needed
- **Batch by default** - validates hundreds of files in seconds
- **Google-specific rules** - checks the exact fields Google requires for rich results, not just schema.org validity
- **Zero dependencies** - pure Python stdlib, runs anywhere Python 3.6+ exists

## Extending

### Adding new schema types

Add a new `elif` block in the `check_google_rules()` function:

```python
elif t == "MyNewType":
    if not has_val(item.get("requiredField")):
        issues.append(issue("error", t, "requiredField", "missing required 'requiredField'"))
```

### Adding to KNOWN_TYPES

If Google adds support for new types, add them to the `KNOWN_TYPES` set at the top of the file.

### Custom severity

The severity model (P0/P1/P2) maps to Google's error/warning/info pattern. Adjust per-field severity in the rules to match your team's priorities.

## Background

This tool was built out of necessity while managing a 170+ page multilingual website. Google Search Console reported structured data errors that had been live for weeks. Manual checking with Google's web tools was impractical at that scale.

The research found:
- No public Google Rich Results Test API exists
- No widely-adopted CLI tool covers all three validation layers
- Google has not published official SHACL shapes for their requirements
- The npm/pip ecosystem for schema.org validation is fragmented

So we built one. It runs in under 2 seconds on 170+ pages and catches every error type that GSC reports.

## License

MIT License. See [LICENSE](LICENSE).
