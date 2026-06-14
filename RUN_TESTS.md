# How to Run End-to-End Tests

## Quick Test (No Credentials Required)

Run unit tests to validate all business logic:

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run specific test suites
pytest tests/test_schemas.py -v
pytest tests/test_pipeline.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

## Full End-to-End Test (Requires Credentials)

### Step 1: Get API Keys

1. **NVIDIA NIM API Key** (Free Tier)
   - Visit: https://build.nvidia.com/
   - Sign up for free account
   - Generate API key
   - Copy key (starts with `nvapi-`)

2. **Tavily Search API Key** (Free Tier)
   - Visit: https://tavily.com/
   - Sign up for free account
   - Generate API key
   - Copy key (starts with `tvly-`)

3. **Slack Webhook** (Optional)
   - Visit: https://api.slack.com/messaging/webhooks
   - Create incoming webhook
   - Select channel for notifications
   - Copy webhook URL

### Step 2: Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env and add your keys
# Use your favorite text editor
notepad .env  # Windows
# or
nano .env     # Linux/Mac
```

Your `.env` should look like:
```env
NVIDIA_API_KEY=nvapi-YOUR-ACTUAL-KEY-HERE
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.1-70b-instruct

TAVILY_API_KEY=tvly-YOUR-ACTUAL-KEY-HERE

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

CHROMA_HOST=chromadb
CHROMA_PORT=8000

LOG_LEVEL=INFO
```

### Step 3: Start Services

```bash
# Build and start all containers
docker-compose up --build

# Or run in detached mode
docker-compose up --build -d

# Check logs
docker-compose logs -f

# Wait for services to be ready (look for these messages):
# - chromadb: "Heartbeat check passed"
# - app: "Application startup complete"
```

### Step 4: Run Test Commands

#### Test 1: Health Check
```bash
curl http://localhost:8000/health
```

Expected output:
```json
{"status":"ok","chroma":true,"llm":true}
```

✅ **Pass Criteria**: Both `chroma` and `llm` are `true`

---

#### Test 2: Analyze Valid Company
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"company": "Notion"}'
```

Expected: HTTP 200 with JSON containing:
- `executive_summary` (string, ≤150 words)
- `competitor_matrix` (markdown table)
- `recommendations` (array with exactly 3 items)
- `brief_markdown` (full report)
- `generated_at` (ISO timestamp)

✅ **Pass Criteria**: 
- Status code: 200
- Response has all required fields
- `recommendations` array length === 3
- `executive_summary` word count ≤ 150

---

#### Test 3: Invalid Input (Empty Company)
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"company": ""}'
```

Expected: HTTP 422 with error message

✅ **Pass Criteria**:
- Status code: 422
- Error message: "Company name must be at least 2 characters"
- `failed_at`: "validate_input"

---

#### Test 4: Invalid Input (Generic Company)
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"company": "company"}'
```

Expected: HTTP 422 with error message

✅ **Pass Criteria**:
- Status code: 422
- Error message contains "generic"

---

#### Test 5: Web Interface
```bash
# Open in browser
http://localhost:8000
```

Manual checks:
- ✅ Page loads without errors
- ✅ Input field accepts text
- ✅ Submit button is clickable
- ✅ Loading spinner appears on submit
- ✅ Results display after analysis
- ✅ Tables are formatted correctly
- ✅ "New Analysis" button works

---

#### Test 6: Compare Endpoint
```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"company_a": "Notion", "company_b": "Obsidian"}'
```

Expected: HTTP 200 with comparison data (takes 180-240 seconds)

✅ **Pass Criteria**:
- Status code: 200
- Response has `company_a` and `company_b`
- `recommendations` has 3 items for each company
- `comparison_matrix` is present

---

#### Test 7: Slack Notification (If Configured)
```bash
# Run an analysis
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"company": "Notion"}'

# Check your Slack channel
```

✅ **Pass Criteria**:
- Message appears in Slack channel
- Message contains company name in bold
- Message contains executive summary

---

### Step 5: Automated Test Script (PowerShell)

```powershell
# Save as test-api.ps1
$baseUrl = "http://localhost:8000"

Write-Host "Testing Health Endpoint..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "$baseUrl/health"
if ($health.status -eq "ok" -and $health.chroma -and $health.llm) {
    Write-Host "✓ Health check passed" -ForegroundColor Green
} else {
    Write-Host "✗ Health check failed" -ForegroundColor Red
}

Write-Host "`nTesting Invalid Input..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/analyze" `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"company": ""}'
    Write-Host "✗ Should have returned 422" -ForegroundColor Red
} catch {
    if ($_.Exception.Response.StatusCode -eq 422) {
        Write-Host "✓ Validation error handled correctly" -ForegroundColor Green
    } else {
        Write-Host "✗ Unexpected error" -ForegroundColor Red
    }
}

Write-Host "`nTesting Valid Analysis (this takes 60-90 seconds)..." -ForegroundColor Cyan
$result = Invoke-RestMethod -Uri "$baseUrl/analyze" `
    -Method Post `
    -ContentType "application/json" `
    -Body '{"company": "Notion"}'

if ($result.recommendations.Count -eq 3) {
    Write-Host "✓ Got exactly 3 recommendations" -ForegroundColor Green
} else {
    Write-Host "✗ Expected 3 recommendations, got $($result.recommendations.Count)" -ForegroundColor Red
}

if ($result.executive_summary) {
    $wordCount = ($result.executive_summary -split '\s+').Count
    if ($wordCount -le 150) {
        Write-Host "✓ Executive summary within limit ($wordCount words)" -ForegroundColor Green
    } else {
        Write-Host "✗ Executive summary too long ($wordCount words)" -ForegroundColor Red
    }
}

Write-Host "`nAll tests completed!" -ForegroundColor Cyan
```

Run the script:
```powershell
.\test-api.ps1
```

---

### Step 6: Cleanup

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (clears ChromaDB data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

---

## Troubleshooting

### Issue: "Connection refused"
**Solution**: Wait longer for services to start. Check logs:
```bash
docker-compose logs -f
```

### Issue: "Invalid API key"
**Solution**: Verify your API keys in `.env` file. Make sure there are no quotes or extra spaces.

### Issue: "ChromaDB not healthy"
**Solution**: ChromaDB may take 30-60 seconds to initialize. Wait and retry.

### Issue: "Analysis times out"
**Solution**: 
- Increase Docker container memory (Settings → Resources)
- Check NVIDIA NIM API rate limits
- Try a different company name

### Issue: "No competitive data found"
**Solution**: Try a more well-known company name (e.g., "Notion", "Slack", "Figma")

---

## Performance Benchmarks

Expected timings on typical hardware:
- Health check: <1s
- Validate input: <1s
- Analyze (full pipeline): 60-90s
- Compare (two analyses): 180-240s

Factors affecting performance:
- NVIDIA NIM API response time
- Tavily search latency
- Network bandwidth
- Docker container resources
