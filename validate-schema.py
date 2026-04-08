#!/usr/bin/env python3
"""
Validate JSON-LD structured data across HTML pages.

Three validation layers:
  Layer 1: JSON syntax — valid JSON, no parsing errors, bad character detection
  Layer 2: Schema.org basics — @context, @type, known vocabulary
  Layer 3: Google Rich Results rules — required/recommended fields per type

Severity levels:
  P0 error   — blocks rich results (invalid JSON, missing required fields)
  P1 warning — missing recommended field (won't block but limits snippets)
  P2 info    — non-standard usage, suggestions

Usage:
  python3 validate-schema.py <html-root>                 # validate all HTML files
  python3 validate-schema.py --file path/to/page.html    # validate single file
  python3 validate-schema.py <html-root> --verbose        # include P2 info
  python3 validate-schema.py <html-root> --json           # JSON report to stdout

Examples:
  python3 validate-schema.py pub-www/
  python3 validate-schema.py public/
  python3 validate-schema.py dist/ --verbose
  python3 validate-schema.py --file pub-www/en/how.html
"""

import json
import re
import os
import sys
import glob

# ──────────────────────────────────────────────────────────────
# Known schema.org types (comprehensive subset)
# ──────────────────────────────────────────────────────────────
KNOWN_TYPES = {
    "AboutPage", "Action", "AggregateRating", "Answer", "Article",
    "Audience", "BlogPosting", "Brand", "BreadcrumbList", "CheckoutPage",
    "CollectionPage", "ContactPage", "ContactPoint", "Course",
    "CreativeWork", "DataCatalog", "Dataset", "DefinedRegion",
    "EducationalOrganization", "EmailMessage", "Event", "FAQPage",
    "HowTo", "HowToDirection", "HowToSection", "HowToStep", "HowToTip",
    "ImageGallery", "ImageObject", "Intangible", "ItemList",
    "ItemPage", "JobPosting", "ListItem", "LocalBusiness",
    "MedicalWebPage", "MerchantReturnPolicy", "MonetaryAmount",
    "Movie", "MusicAlbum", "MusicGroup", "MusicRecording",
    "NewsArticle", "Offer", "OfferCatalog", "OfferShippingDetails",
    "Organization", "Person", "Place", "PostalAddress",
    "PriceSpecification", "Product", "ProfilePage", "Project",
    "PropertyValue", "QAPage", "QuantitativeValue", "Question",
    "Rating", "Recipe", "Review", "SearchAction",
    "SearchResultsPage", "Service", "ShippingDeliveryTime",
    "SiteNavigationElement", "SoftwareApplication", "SoftwareSourceCode",
    "SpecialAnnouncement", "Thing", "VideoObject", "VisualArtwork",
    "WebApplication", "WebPage", "WebSite",
}

# Characters that break JSON parsing
BAD_CHARS = {
    "\u201c": "left curly double quote",
    "\u201d": "right curly double quote",
}


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def has_val(v):
    """Check if a value is present and non-empty."""
    return v is not None and v != "" and v != []


def as_list(v):
    """Normalize to list."""
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def get_offer_targets(offers_val):
    """Return actual Offer dicts, resolving OfferCatalog and skipping @id refs."""
    if not isinstance(offers_val, dict):
        return [offers_val] if offers_val else []
    if "@id" in offers_val and "@type" not in offers_val:
        return []  # pure reference
    if offers_val.get("@type") == "OfferCatalog":
        return [i for i in offers_val.get("itemListElement", []) if isinstance(i, dict)]
    return [offers_val]


def issue(severity, schema_type, field, message):
    """Create an issue tuple."""
    return (severity, f"{schema_type}: {message}" + (f" [{field}]" if field else ""))


# ──────────────────────────────────────────────────────────────
# Layer 1: JSON syntax + bad chars
# ──────────────────────────────────────────────────────────────
def extract_jsonld(html):
    """Extract all JSON-LD script blocks from HTML."""
    pattern = r'<script\s+type="application/ld\+json">(.*?)</script>'
    return re.findall(pattern, html, re.DOTALL)


def check_bad_chars(raw_json):
    """Check for characters that break JSON parsing."""
    issues = []
    for i, line in enumerate(raw_json.split("\n"), 1):
        for char, name in BAD_CHARS.items():
            if char in line:
                issues.append(f"  LINE {i}: {name} found")
    return issues


# ──────────────────────────────────────────────────────────────
# Layer 2: Schema.org basics
# ──────────────────────────────────────────────────────────────
def check_schema_basics(data):
    """Check @context and @type basics."""
    issues = []

    ctx = data.get("@context", "")
    if not ctx:
        issues.append(("error", "Missing @context — JSON-LD requires @context"))
    elif "schema.org" not in str(ctx):
        issues.append(("warning", f"Unexpected @context: {ctx}"))

    graph = data.get("@graph", [data])
    for item in graph:
        t = item.get("@type", "")
        if not t:
            item_id = item.get("@id", "unknown")
            if "@id" in item and len(item) <= 2:
                continue
            issues.append(("error", f"Item missing @type (id: {item_id})"))
        elif t not in KNOWN_TYPES:
            issues.append(("error", f"Unknown @type '{t}' — not in schema.org vocabulary"))

    return issues


# ──────────────────────────────────────────────────────────────
# Layer 3: Google Rich Results rules
# ──────────────────────────────────────────────────────────────
def check_google_rules(item):
    """Check Google-specific required/recommended fields for a schema item."""
    t = item.get("@type", "")
    issues = []

    # ── Article / NewsArticle / BlogPosting ──
    if t in ("Article", "NewsArticle", "BlogPosting"):
        for field in ("headline", "datePublished", "author"):
            if not has_val(item.get(field)):
                issues.append(issue("error", t, field, f"missing required '{field}'"))
        for field in ("image", "publisher", "dateModified"):
            if not has_val(item.get(field)):
                issues.append(issue("warning", t, field, f"missing recommended '{field}'"))

    # ── FAQPage ──
    elif t == "FAQPage":
        questions = as_list(item.get("mainEntity"))
        if not questions:
            issues.append(issue("error", t, "mainEntity", "requires at least one Question"))
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                issues.append(issue("error", t, f"mainEntity[{i}]", "must be an object"))
                continue
            if q.get("@type") != "Question":
                issues.append(issue("error", t, f"mainEntity[{i}].@type", "must be 'Question'"))
            if not has_val(q.get("name")):
                issues.append(issue("error", t, f"mainEntity[{i}].name", "Question missing name"))
            ans = q.get("acceptedAnswer", {})
            if not isinstance(ans, dict) or ans.get("@type") != "Answer":
                issues.append(issue("error", t, f"mainEntity[{i}].acceptedAnswer", "requires Answer type"))
            elif not has_val(ans.get("text")):
                issues.append(issue("error", t, f"mainEntity[{i}].acceptedAnswer.text", "Answer missing text"))

    # ── HowTo ──
    elif t == "HowTo":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        steps = as_list(item.get("step"))
        if not steps:
            issues.append(issue("error", t, "step", "requires at least one step"))
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            st = step.get("@type", "")
            if st == "HowToSection":
                inner_steps = as_list(step.get("itemListElement"))
                if not inner_steps:
                    issues.append(issue("warning", t, f"step[{i}].itemListElement", "HowToSection has no steps"))
                for j, inner in enumerate(inner_steps):
                    if isinstance(inner, dict) and not has_val(inner.get("text")) and not has_val(inner.get("name")):
                        issues.append(issue("warning", t, f"step[{i}].itemListElement[{j}]", "HowToStep missing name or text"))
            elif st == "HowToStep":
                if not has_val(step.get("text")) and not has_val(step.get("name")):
                    issues.append(issue("warning", t, f"step[{i}]", "HowToStep missing name or text"))
        if not has_val(item.get("image")):
            issues.append(issue("info", t, "image", "missing recommended 'image'"))

    # ── Product ──
    elif t == "Product":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("image")):
            issues.append(issue("warning", t, "image", "missing recommended 'image'"))
        if not has_val(item.get("brand")):
            issues.append(issue("warning", t, "brand", "missing recommended 'brand'"))
        issues.extend(_check_offers(item, t))

    # ── SoftwareApplication ──
    elif t == "SoftwareApplication":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("applicationCategory")):
            issues.append(issue("info", t, "applicationCategory", "missing recommended 'applicationCategory'"))
        issues.extend(_check_offers(item, t))

    # ── WebApplication (lighter checks — often embedded tools/calculators) ──
    elif t == "WebApplication":
        if not has_val(item.get("name")):
            issues.append(issue("warning", t, "name", "missing recommended 'name'"))

    # ── Event ──
    elif t == "Event":
        for field in ("name", "startDate", "location"):
            if not has_val(item.get(field)):
                issues.append(issue("error", t, field, f"missing required '{field}'"))
        if not has_val(item.get("endDate")):
            issues.append(issue("warning", t, "endDate", "missing recommended 'endDate'"))
        if not has_val(item.get("description")):
            issues.append(issue("warning", t, "description", "missing recommended 'description'"))

    # ── JobPosting ──
    elif t == "JobPosting":
        for field in ("title", "description", "datePosted", "hiringOrganization"):
            if not has_val(item.get(field)):
                issues.append(issue("error", t, field, f"missing required '{field}'"))
        if not has_val(item.get("validThrough")):
            issues.append(issue("warning", t, "validThrough", "missing recommended 'validThrough'"))
        if not has_val(item.get("employmentType")):
            issues.append(issue("warning", t, "employmentType", "missing recommended 'employmentType'"))

    # ── Recipe ──
    elif t == "Recipe":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("image")):
            issues.append(issue("error", t, "image", "missing required 'image'"))
        for field in ("author", "prepTime", "cookTime", "recipeIngredient", "recipeInstructions"):
            if not has_val(item.get(field)):
                issues.append(issue("warning", t, field, f"missing recommended '{field}'"))

    # ── Course ──
    elif t == "Course":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("description")):
            issues.append(issue("error", t, "description", "missing required 'description'"))
        if not has_val(item.get("provider")):
            issues.append(issue("warning", t, "provider", "missing recommended 'provider'"))

    # ── Review ──
    elif t == "Review":
        if not has_val(item.get("reviewRating")):
            issues.append(issue("error", t, "reviewRating", "missing required 'reviewRating'"))
        if not has_val(item.get("author")):
            issues.append(issue("error", t, "author", "missing required 'author'"))
        if not has_val(item.get("itemReviewed")):
            issues.append(issue("warning", t, "itemReviewed", "missing recommended 'itemReviewed'"))

    # ── VideoObject ──
    elif t == "VideoObject":
        for field in ("name", "description", "thumbnailUrl", "uploadDate"):
            if not has_val(item.get(field)):
                issues.append(issue("error", t, field, f"missing required '{field}'"))

    # ── LocalBusiness ──
    elif t == "LocalBusiness":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("address")):
            issues.append(issue("error", t, "address", "missing required 'address'"))
        for field in ("telephone", "openingHoursSpecification", "image"):
            if not has_val(item.get(field)):
                issues.append(issue("warning", t, field, f"missing recommended '{field}'"))

    # ── Organization ──
    elif t == "Organization":
        if not has_val(item.get("name")):
            issues.append(issue("warning", t, "name", "missing recommended 'name'"))
        if not has_val(item.get("url")):
            issues.append(issue("warning", t, "url", "missing recommended 'url'"))
        if not has_val(item.get("logo")):
            issues.append(issue("info", t, "logo", "missing recommended 'logo'"))

    # ── WebSite ──
    elif t == "WebSite":
        if not has_val(item.get("url")):
            issues.append(issue("warning", t, "url", "missing recommended 'url'"))

    # ── WebPage / AboutPage / ItemPage / etc. ──
    elif t in ("WebPage", "AboutPage", "ItemPage", "CollectionPage",
               "SearchResultsPage", "CheckoutPage", "ContactPage",
               "MedicalWebPage", "ProfilePage", "QAPage"):
        if not has_val(item.get("name")) and not has_val(item.get("headline")):
            issues.append(issue("warning", t, "name", "missing recommended 'name' or 'headline'"))
        if not has_val(item.get("url")):
            issues.append(issue("warning", t, "url", "missing recommended 'url'"))
        bc = item.get("breadcrumb")
        if isinstance(bc, dict):
            issues.extend(_check_breadcrumb(bc))

    # ── BreadcrumbList (standalone) ──
    elif t == "BreadcrumbList":
        issues.extend(_check_breadcrumb(item))

    # ── Service ──
    elif t == "Service":
        if not has_val(item.get("name")):
            issues.append(issue("warning", t, "name", "missing recommended 'name'"))

    # ── CreativeWork ──
    elif t == "CreativeWork":
        if not has_val(item.get("name")) and not has_val(item.get("headline")):
            issues.append(issue("info", t, "name", "missing recommended 'name' or 'headline'"))

    # ── Dataset ──
    elif t == "Dataset":
        if not has_val(item.get("name")):
            issues.append(issue("error", t, "name", "missing required 'name'"))
        if not has_val(item.get("description")):
            issues.append(issue("error", t, "description", "missing required 'description'"))

    return issues


def _check_offers(item, parent_type):
    """Check Offer fields within a parent type."""
    issues = []
    offers_val = item.get("offers")
    if not has_val(offers_val):
        issues.append(issue("warning", parent_type, "offers", "missing recommended 'offers'"))
        return issues

    targets = get_offer_targets(offers_val)
    if not targets:
        return issues  # @id reference — skip

    for j, offer in enumerate(targets):
        if not isinstance(offer, dict):
            continue
        suffix = f"[{j}]" if len(targets) > 1 else ""
        prefix = f"offers{suffix}"

        if not has_val(offer.get("price")) and not has_val(offer.get("priceSpecification")):
            issues.append(issue("warning", parent_type, f"{prefix}.price", "Offer missing price or priceSpecification"))
        if has_val(offer.get("price")) and not has_val(offer.get("priceCurrency")):
            issues.append(issue("warning", parent_type, f"{prefix}.priceCurrency", "Offer has price but missing priceCurrency"))
        if not has_val(offer.get("availability")):
            issues.append(issue("info", parent_type, f"{prefix}.availability", "Offer missing recommended 'availability'"))
        if not has_val(offer.get("hasMerchantReturnPolicy")):
            issues.append(issue("warning", parent_type, f"{prefix}.hasMerchantReturnPolicy", "Offer missing recommended 'hasMerchantReturnPolicy'"))

        shipping = offer.get("shippingDetails")
        if not has_val(shipping):
            issues.append(issue("warning", parent_type, f"{prefix}.shippingDetails", "Offer missing recommended 'shippingDetails'"))
        elif isinstance(shipping, dict):
            if not has_val(shipping.get("deliveryTime")):
                issues.append(issue("warning", parent_type, f"{prefix}.shippingDetails.deliveryTime", "shippingDetails missing 'deliveryTime'"))

    return issues


def _check_breadcrumb(bc):
    """Validate BreadcrumbList structure."""
    issues = []
    items = as_list(bc.get("itemListElement"))
    if not items:
        issues.append(issue("error", "BreadcrumbList", "itemListElement", "requires at least one ListItem"))
        return issues
    for i, li in enumerate(items):
        if not isinstance(li, dict):
            issues.append(issue("error", "BreadcrumbList", f"itemListElement[{i}]", "must be an object"))
            continue
        if li.get("@type") != "ListItem":
            issues.append(issue("error", "BreadcrumbList", f"itemListElement[{i}].@type", "must be 'ListItem'"))
        if not has_val(li.get("position")):
            issues.append(issue("error", "BreadcrumbList", f"itemListElement[{i}].position", "ListItem missing position"))
        if not has_val(li.get("name")):
            issues.append(issue("error", "BreadcrumbList", f"itemListElement[{i}].name", "ListItem missing name"))
    return issues


# ──────────────────────────────────────────────────────────────
# Main validation pipeline
# ──────────────────────────────────────────────────────────────
def validate_file(filepath, verbose=False):
    """Run all validation layers on a single HTML file."""
    with open(filepath, encoding="utf-8") as f:
        html = f.read()

    blocks = extract_jsonld(html)
    if not blocks:
        return [("info", "No JSON-LD found")]

    all_issues = []
    for idx, raw in enumerate(blocks):
        char_issues = check_bad_chars(raw)
        if char_issues:
            all_issues.append(("error", "Bad characters in JSON-LD:\n" + "\n".join(char_issues)))

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            all_issues.append(("error", f"JSON parse error: {e}"))
            continue

        all_issues.extend(check_schema_basics(data))

        graph = data.get("@graph", [data])
        if verbose:
            types = [item.get("@type", "?") for item in graph]
            all_issues.append(("info", f"Block {idx+1}: @graph has {len(graph)} items: {', '.join(types)}"))

        for item in graph:
            all_issues.extend(check_google_rules(item))

    return all_issues


def find_html_root():
    """Auto-detect HTML root directory from common conventions."""
    cwd = os.getcwd()
    candidates = ["pub-www", "public", "dist", "build", "out", "_site", "www", "site", "."]
    for c in candidates:
        path = os.path.join(cwd, c)
        if os.path.isdir(path):
            htmls = glob.glob(os.path.join(path, "**", "*.html"), recursive=True)
            if htmls:
                return path
    return None


def main():
    verbose = "--verbose" in sys.argv
    json_output = "--json" in sys.argv
    single_file = None
    html_root = None

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for i, arg in enumerate(sys.argv):
        if arg == "--file" and i + 1 < len(sys.argv):
            single_file = sys.argv[i + 1]

    if single_file:
        files = [single_file]
        html_root = os.path.dirname(single_file)
    elif args:
        html_root = args[0]
        if not os.path.isdir(html_root):
            print(f"Error: '{html_root}' is not a directory", file=sys.stderr)
            return 1
        files = sorted(glob.glob(os.path.join(html_root, "**", "*.html"), recursive=True))
    else:
        html_root = find_html_root()
        if html_root:
            if not json_output:
                print(f"Auto-detected HTML root: {html_root}/")
            files = sorted(glob.glob(os.path.join(html_root, "**", "*.html"), recursive=True))
        else:
            print("Error: No HTML root found. Pass a directory as argument.", file=sys.stderr)
            print("Usage: python3 validate-schema.py <html-root>", file=sys.stderr)
            return 1

    if not files:
        print(f"No HTML files found in {html_root}/", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0
    total_infos = 0
    clean_files = 0
    report = []

    for filepath in files:
        relpath = os.path.relpath(filepath, html_root) if html_root else filepath
        all_issues = validate_file(filepath, verbose)

        errors = [i for i in all_issues if i[0] == "error"]
        warnings = [i for i in all_issues if i[0] == "warning"]
        infos = [i for i in all_issues if i[0] == "info"]

        if json_output:
            for severity, msg in all_issues:
                if severity != "info" or verbose:
                    report.append({"file": relpath, "severity": severity, "message": msg})

        if errors or warnings:
            if not json_output:
                icon = "P0" if errors else "P1"
                print(f"\n{icon} {relpath}")
                for _, msg in errors:
                    print(f"  ERROR: {msg}")
                    total_errors += 1
                for _, msg in warnings:
                    print(f"  WARN:  {msg}")
                    total_warnings += 1
                if verbose:
                    for _, msg in infos:
                        print(f"  INFO:  {msg}")
                        total_infos += 1
        else:
            clean_files += 1
            if verbose and not json_output:
                print(f"\nOK {relpath}")
                for _, msg in infos:
                    print(f"  INFO:  {msg}")
                    total_infos += 1

    if json_output:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        print(f"\n{'='*60}")
        print(f"SUMMARY: {len(files)} files scanned")
        print(f"  OK  {clean_files} clean")
        print(f"  P0  {total_errors} errors (blocks rich results)")
        print(f"  P1  {total_warnings} warnings (limits snippets)")
        if verbose:
            print(f"  P2  {total_infos} info")
        print()
        if total_errors == 0 and total_warnings == 0:
            print("All pages pass Google Rich Results validation.")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
