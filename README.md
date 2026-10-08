# KPI Audit Engine

Deterministic KPI validation for manufacturing and Lean consulting. Built from six supplied Advent Engineers, Entech Controls and R&D Therm G12 workbooks. The hosted application processes `.xlsx` files in the browser; source files are never transmitted or modified.

## Use the application

1. Open the private Site and choose **New audit**.
2. Select a company’s Master and MCLS workbooks together. You may select all six reference files in one audit.
3. Review Critical, Warning and Review Required groups. Select a finding to see formulas, source locations, expected values and downstream effects.
4. Open **Workbook explorer** for sheet classification and semantic field mappings; **KPI results** for independent calculations and trends.
5. Use **Company settings** for company-specific targets, benchmark, formula, unit and aggregation overrides. In **KPI rulebook**, edit or approve the underlying rules. Run a new audit after changing rules.
6. Export an Excel, CSV or JSON report. **Print / save PDF** opens the browser’s PDF printing flow.

History is off by default. If enabled, only report data (not original files) is saved in IndexedDB on that device, expiring after 30 days. Delete saved history or clear the current session at any time. Rule changes and company settings are saved separately in localStorage. Source data are never sent to an AI service.

## Implementation

* `dist/engine.mjs`: semantic input mapping, safe AST formula evaluator, independent business arithmetic, formula normalization, dependencies, validation, cumulative aggregation and root-cause grouping.
* `dist/rules.mjs`: 20 KPI definitions across the 12 requested families, including explicit ROI and Productivity variants.
* `dist/xlsx.mjs`: ZIP/XML workbook reader, size limits, shared formulas, named ranges, merges, sheet states and XLSX report generation. Uses vendored JSZip 3.10.1 under MIT/GPL dual licensing; MIT selected.
* `dist/app.mjs`, `dist/style.css`: responsive dashboard, filters, evidence dialogs, rulebook editor, company overrides, dependency views, optional local history and report downloads. Browser-native modules keep confidential processing local and require no frontend build service.
* `scripts/inspect_workbooks.py`: read-only openpyxl inventory; formula text and saved values remain distinct. Does not recalculate Excel formulas.
* `api/`: optional FastAPI/PostgreSQL adapter with administrator, auditor and viewer roles; explicit company grants; encrypted report payloads; deletion and retention. This is separate from the hosted browser edition.
* `docs/`: reference discovery, workbook architecture and regression summary.

This version uses browser-native JavaScript instead of the prompt’s recommended React/TypeScript frontend. The deterministic engine is a shared module used by both the private browser application and the optional Python API. PostgreSQL is used only in the standalone API deployment, not the Sites browser edition.

## Local development and tests

Node 22+ and Python 3.12+ recommended. No Node install is needed for the static application or core engine tests.

```sh
node --test tests/*.test.mjs
python -m http.server 8080 --directory dist
```

Open `http://localhost:8080`. The application fetches its reference candidates locally and requires an HTTP origin; do not launch `index.html` as a `file://` URL.

For read-only reference discovery (Python openpyxl required):

```sh
python scripts/inspect_workbooks.py /path/to/workbooks /tmp/kpi-discovery
node scripts/audit.mjs /tmp/kpi-discovery/*G12*.json > /tmp/kpi-audit.json
node tests/xlsx-integration.mjs /path/to/workbooks /tmp/browser-audit.json
```

The integration test exercises the actual browser XLSX parser through a test-only XML DOM adapter; it is not a visual browser test. Raw client workbooks and full results are intentionally excluded from source control. Regenerate the detailed results from authorized local files.

## Standalone API deployment

The API runtime was not deployed or integration-tested in this environment. Python syntax is checked. Before production, run service integration tests against PostgreSQL, confirm HTTPS, credential rotation and company grants, and review API retention and backup policy.

Set environment variables securely:

* `POSTGRES_PASSWORD`: strong PostgreSQL password (compose).
* `DATABASE_URL`: PostgreSQL connection URI (set by compose).
* `KPI_ENCRYPTION_KEY`: Fernet key; retain securely for decrypting saved audits.
* `KPI_USERS_JSON`: JSON array of `{ "id": "...", "role": "admin|auditor|viewer", "token_sha256": "...", "companies": ["Exact company name"] }`.
* `KPI_RETENTION_DAYS`: defaults to 30, range 1–365.

Generate a random API token outside source control and store only its SHA-256 digest in the configured user record. API clients send `Authorization: Bearer <token>`. Tokens are not printed by the application. The API starts only with required configuration.

```sh
docker compose up --build -d
```

The service binds to localhost port 8000; terminate TLS with your reverse proxy. Endpoints: `POST /api/audits`, `GET /api/audits`, `GET/DELETE /api/audits/{id}`, `GET/PUT /api/rulebook`, `GET /api/health`. Company access is explicitly configured per user. Audit metadata records company identity; report payloads are encrypted at application level. Raw uploads are temporary and deleted after processing, including failures. Retention cleanup runs on authenticated audit operations; use an external scheduled cleanup if deletion must occur while the API is idle. Browser UI stays in local mode; there is no misleading server-login toggle.

## Verification boundaries

* Unsupported functions, unavailable external sources, zero denominators and ambiguous mappings do not pass silently.
* Reference-specific Productivity, ROI and ITR cumulative rules are not approximated. Explicit inventory/capital aggregation approval is required.
* A YTD discrepancy with uncertain phase/year boundaries is a review item, not an automatic critical error.
* Targets and benchmarks are company configuration; missed targets are operational observations.
* Recognition/certificate inputs are mapped but qualitative validity cannot be verified automatically.
* Duplicate monthly headers are detected; identical order/training records without reliable record identifiers are not automatically classified as duplicates.
* Financial adjustments may legitimately be negative; physical numerator/denominator constraints are handled separately.
* Data validation confidence is scoped to evaluable checks and is shown next to coverage. It is not an overall health score or operational performance score.

## GitHub repository

Source repository: https://github.com/geetahuja/curly-barnacle (private).

Hosted application: https://kpi-audit-engine.shady-krill-5614.chatgpt.site

The initial application source was uploaded on 8 October 2026 using the authorized geetahuja account. The original repository history is preserved. Confidential source workbooks, full audit results, secrets and credentials are excluded.

GitHub stores the source; the private Site has a separate publishing workflow. Pushing a commit to GitHub does not automatically deploy the Site. The standalone API remains an optional, undeployed component; see the verification boundaries above.
