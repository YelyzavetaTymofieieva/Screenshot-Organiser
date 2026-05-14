# 📸 Screenshot Organiser — Project Plan

> **Stack:** Python · Streamlit · AWS (Terraform) · Claude Vision API  
> **Goal:** Zero-effort screenshot organisation — take a screenshot, everything else is automatic  
> **Cost target:** $0–2/month on AWS Free Tier + credits

---

## 🧭 Overview

```
[Mac Screenshot] → [watchdog daemon] → [FastAPI] → [Claude Vision]
                                                          ↓
                                          Classify + Extract structured content
                                                          ↓
                                    ┌─────────────────────┴─────────────────────┐
                               Save to S3                               Mark as "junk"
                          (recipes / vocab /                        → move to Unclassified
                           products / notes)                           review in UI
                                    ↓
                           Streamlit Dashboard
                        (browse folders, search,
                          confirm deletions)
```

---

## 📁 Project Structure

```
screenshot-organiser/
├── infra/                          # Terraform AWS infrastructure
│   ├── main.tf
│   ├── s3.tf
│   ├── dynamodb.tf
│   ├── lambda.tf
│   ├── iam.tf
│   └── variables.tf
├── backend/
│   ├── daemon/
│   │   └── watcher.py              # watchdog — monitors Screenshots folder
│   ├── api/
│   │   ├── main.py                 # FastAPI app
│   │   ├── routes/
│   │   │   ├── upload.py           # receive image, trigger processing
│   │   │   └── notes.py            # CRUD for organised notes
│   │   ├── services/
│   │   │   ├── vision.py           # Claude Vision API calls
│   │   │   ├── classifier.py       # category logic
│   │   │   ├── extractor.py        # structured data extraction per category
│   │   │   └── storage.py          # S3 + DynamoDB operations
│   │   └── models/
│   │       └── schemas.py          # Pydantic models
├── frontend/
│   └── app.py                      # Streamlit dashboard
├── requirements.txt
└── README.md
```

---

## 🔬 Business Logic

### 1. Screenshot Detection (daemon/watcher.py)

The daemon runs silently in the background using Python's `watchdog` library. It watches `~/Desktop` or `~/Screenshots` (wherever your Mac saves screenshots by default).

**Trigger conditions:**
- New `.png` / `.jpg` file appears in watched folder
- File name matches Mac screenshot pattern: `Screenshot YYYY-MM-DD at HH.MM.SS.png`
- Wait 1 second after creation (ensures file is fully written)

```python
# Pseudocode
on_new_file(filepath):
    if is_screenshot(filepath):
        wait(1 second)
        POST /api/upload  ← sends image as base64
```

---

### 2. AI Classification (services/vision.py + classifier.py)

Each image is sent to **Claude Vision** (via Anthropic API) with a structured prompt:

**Prompt strategy:**
```
Look at this screenshot and return JSON with:
{
  "category": one of ["recipe", "vocabulary", "product", "quote", "code", "junk"],
  "confidence": 0.0–1.0,
  "title": "short descriptive title",
  "extracted_data": { ... category-specific fields ... },
  "note": "optional short human-readable note"
}
```

**Category rules:**

| Category | What it looks like | Extracted fields |
|---|---|---|
| `recipe` | Ingredients, cooking steps, food photo | title, ingredients[], steps[], cuisine |
| `vocabulary` | English phrase, sentence, word + translation | word, definition, example_sentence, language |
| `product` | Brand name, product shot, beauty/fashion item | brand, product_name, category, note ("check out") |
| `quote` | Inspirational text, book quote, tweet | text, author, source |
| `code` | Code snippet, terminal output | language, snippet, description |
| `junk` | Meme with no info, blurry, irrelevant | — |

**Confidence threshold:**
- `>= 0.75` → auto-categorise and save
- `0.5–0.74` → save to **Unclassified** for manual review
- `< 0.5` → mark as junk, do not save

---

### 3. Storage Logic (services/storage.py)

**On successful classification:**
1. Upload original screenshot to S3: `s3://your-bucket/{category}/{YYYY-MM}/{uuid}.png`
2. Save structured metadata to DynamoDB
3. Delete original file from local disk

**On junk / low confidence:**
1. Move file to local `~/Screenshots/Unclassified/` folder
2. Do NOT upload to S3
3. User reviews from Streamlit UI and can confirm delete or re-categorise

---

### 4. Streamlit Dashboard (frontend/app.py)

**Pages / sections:**

```
Sidebar:
  📁 All Notes
  📁 Recipes
  📁 Vocabulary
  📁 Products
  📁 Quotes
  📁 Code Snippets
  📁 Unclassified (review queue)
  ⚙️  Settings

Main area:
  - Card grid of notes with title, category badge, date
  - Click to expand full extracted content
  - Search bar (searches titles + content)
  - "Delete" and "Move to folder" actions
  - Unclassified: shows image + AI's best guess → Confirm / Re-categorise / Delete
```

---

## ☁️ AWS Infrastructure (Terraform)

### Services used & why they're near-free

| Service | Usage | Free Tier / Cost |
|---|---|---|
| **S3** | Store screenshots + notes | 5 GB free, then ~$0.02/GB |
| **DynamoDB** | Metadata, search index | 25 GB free forever |
| **Lambda** | Optional: async processing trigger | 1M requests/month free |
| **CloudWatch** | Logs from daemon + API | 5 GB free |
| **IAM** | Access control | Always free |

> **Anthropic API** is the only real cost. Claude Haiku is ~$0.25 per million input tokens. Processing ~100 screenshots/month ≈ **< $0.10/month**.

---

### Terraform File Breakdown

#### `infra/s3.tf`
```hcl
resource "aws_s3_bucket" "screenshots" {
  bucket = "screenshot-organiser-${var.environment}"
}

resource "aws_s3_bucket_lifecycle_configuration" "cleanup" {
  bucket = aws_s3_bucket.screenshots.id

  rule {
    id     = "expire-junk"
    status = "Enabled"

    filter {
      prefix = "unclassified/"
    }

    expiration {
      days = 30   # auto-delete unclassified after 30 days
    }
  }
}

resource "aws_s3_bucket_versioning" "screenshots" {
  bucket = aws_s3_bucket.screenshots.id
  versioning_configuration {
    status = "Disabled"   # keep costs minimal
  }
}
```

#### `infra/dynamodb.tf`
```hcl
resource "aws_dynamodb_table" "notes" {
  name         = "screenshot-notes"
  billing_mode = "PAY_PER_REQUEST"   # no provisioned capacity = free at low volume
  hash_key     = "id"
  range_key    = "created_at"

  attribute {
    name = "id"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  attribute {
    name = "category"
    type = "S"
  }

  global_secondary_index {
    name            = "CategoryIndex"
    hash_key        = "category"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = {
    Project = "screenshot-organiser"
  }
}
```

#### `infra/iam.tf`
```hcl
resource "aws_iam_user" "app_user" {
  name = "screenshot-organiser-app"
}

resource "aws_iam_user_policy" "app_policy" {
  name = "screenshot-organiser-policy"
  user = aws_iam_user.app_user.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.screenshots.arn,
          "${aws_s3_bucket.screenshots.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.notes.arn
      }
    ]
  })
}
```

#### `infra/variables.tf`
```hcl
variable "environment" {
  default = "dev"
}

variable "aws_region" {
  default = "eu-west-1"
}
```

#### `infra/main.tf`
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
```

---

## 🗺️ Milestones

### Milestone 1 — Core Pipeline (Week 1–2)
**Goal:** Screenshot → Claude → structured JSON working end to end

- [ ] Set up Python project with FastAPI + `requirements.txt`
- [ ] Implement `watcher.py` using `watchdog`
- [ ] Write `vision.py` — call Claude Vision API, parse JSON response
- [ ] Write `classifier.py` — category routing logic
- [ ] Write `extractor.py` — per-category structured extraction
- [ ] Test locally with 10 real screenshots

**Key libraries:**
```
fastapi
uvicorn
watchdog
anthropic
boto3
python-dotenv
pillow
pydantic
```

---

### Milestone 2 — AWS Storage (Week 2)
**Goal:** Notes saved to S3 + DynamoDB, local file deleted

- [ ] Write Terraform files (S3 + DynamoDB + IAM)
- [ ] Run `terraform init && terraform apply`
- [ ] Implement `storage.py` — S3 upload + DynamoDB write
- [ ] Wire pipeline: watcher → API → vision → storage
- [ ] Test: screenshot appears → auto-deleted → note in DynamoDB ✅

---

### Milestone 3 — Streamlit Dashboard (Week 3)
**Goal:** Browse, search, and manage organised notes

- [ ] Build folder sidebar with category counts
- [ ] Note card grid with category badge + date
- [ ] Click-to-expand with full extracted content
- [ ] Unclassified review queue (confirm / re-categorise / delete)
- [ ] Basic search by title/content
- [ ] Delete confirmation with S3 + DynamoDB cleanup

---

### Milestone 4 — Polish (Week 4)
**Goal:** Reliable, production-ready for personal use

- [ ] Add `.env` config (API keys, S3 bucket, watched folder path)
- [ ] Daemon auto-start on Mac login (launchd plist)
- [ ] Error handling + retry logic for API failures
- [ ] CloudWatch logging for daemon + API
- [ ] README with setup instructions
- [ ] Handle edge cases: duplicate screenshots, very large images, non-English text

---

## 🔧 Local Development Setup

```bash
# 1. Clone and install
git clone https://github.com/yourname/screenshot-organiser
cd screenshot-organiser
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Environment variables
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, WATCH_FOLDER

# 3. Provision AWS
cd infra
terraform init
terraform apply

# 4. Run the API
cd ../backend
uvicorn api.main:app --reload --port 8000

# 5. Run the daemon (separate terminal)
python daemon/watcher.py

# 6. Run Streamlit
cd ../frontend
streamlit run app.py
```

---

## 💸 Cost Breakdown

| Item | Monthly cost |
|---|---|
| S3 (5 GB free tier) | $0 |
| DynamoDB (free tier) | $0 |
| CloudWatch logs | $0 |
| Anthropic API (~100 screenshots @ Claude Haiku) | ~$0.05 |
| **Total** | **~$0.05–$0.50/month** |

> If you process 1,000 screenshots/month (heavy use), cost is still under $1.

---

## 🚀 Future Enhancements (not in scope now)

- **Export to Notion** — sync vocabulary to a Notion database
- **Anki flashcard export** — turn vocabulary notes into `.apkg` files
- **Duplicate detection** — "you saved this brand 2 months ago"
- **Search by image** — find notes that contain a colour / logo
- **Flutter mobile app** — share sheet → same FastAPI backend, new frontend
- **Browser extension** — right-click → save to organiser (for web screenshots)
- **Weekly digest email** — "here's what you saved this week"
