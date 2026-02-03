# VetUltrasound API

> Transforming messy veterinary ultrasound PDFs into clean, structured JSON data.

I built this API to solve a real problem: veterinary clinics generate tons of ultrasound reports as PDFs, but that data is essentially trapped. This service extracts patient info, diagnoses, and recommendations automatically using Google Cloud's Document AI.

## Why I Built This

Manual data entry from PDFs is slow and error-prone. With this API, a clinic can:
1. Upload a PDF report
2. Get back structured JSON in seconds
3. Store and search patient records easily

## Features

- **Secure PDF Upload**: Authenticated endpoint for uploading ultrasound reports
- **Intelligent Data Extraction**: Uses Google Cloud Document AI to extract:
  - Patient information (name, species, breed, age)
  - Owner details (name, contact info)
  - Veterinarian data (name, license, clinic)
  - Diagnosis and findings
  - Treatment recommendations
- **Image Management**: Automatic extraction and storage of ultrasound images
- **RESTful API**: Clean, documented endpoints with OpenAPI specification
- **Production Ready**: Rate limiting, structured logging, health checks

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Client App    │────▶│   Cloud Run     │────▶│  Document AI    │
│  (Postman/CLI)  │     │   (FastAPI)     │     │  (Form Parser)  │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌───────────┐ ┌───────────┐ ┌───────────┐
             │  Cloud    │ │ Firestore │ │  Cloud    │
             │  Storage  │ │ (NoSQL)   │ │  Logging  │
             │  (PDFs)   │ │           │ │           │
             └───────────┘ └───────────┘ └───────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python 3.11) |
| Compute | Google Cloud Run |
| Storage | Google Cloud Storage |
| Database | Cloud Firestore |
| OCR/AI | Document AI (Form Parser) |
| Auth | API Keys + JWT |
| Container | Docker |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents` | Upload PDF for processing |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `GET` | `/api/v1/documents/{id}/images` | Get document images |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document |
| `GET` | `/health` | Health check |

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud Project with billing enabled
- gcloud CLI installed and configured

### Local Development

1. **Clone and setup**
```bash
git clone https://github.com/Santiago20022/tartup-friendly.git
cd tartup-friendly
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your GCP project details
```

3. **Set up GCP authentication**
```bash
gcloud auth application-default login
```

4. **Run locally**
```bash
uvicorn src.main:app --reload --port 8080
```

5. **Test the API**
```bash
# Health check
curl http://localhost:8080/health

# Upload a PDF (with demo API key)
curl -X POST http://localhost:8080/api/v1/documents \
  -H "X-API-Key: demo-api-key-12345" \
  -F "file=@ultrasound-report.pdf"
```

## GCP Setup

### 1. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  documentai.googleapis.com \
  storage.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com
```

### 2. Create Storage Buckets

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=us-central1

# Uploads bucket
gsutil mb -l $REGION gs://${PROJECT_ID}-ultrasound-uploads
gsutil uniformbucketlevelaccess set on gs://${PROJECT_ID}-ultrasound-uploads

# Images bucket
gsutil mb -l $REGION gs://${PROJECT_ID}-ultrasound-images
gsutil uniformbucketlevelaccess set on gs://${PROJECT_ID}-ultrasound-images
```

### 3. Create Document AI Processor

```bash
# Create a Form Parser processor via Console or API
# Navigate to: https://console.cloud.google.com/ai/document-ai
# Create processor type: Form Parser
# Note the processor ID for configuration
```

### 4. Initialize Firestore

```bash
gcloud firestore databases create --region=$REGION
```

### 5. Deploy to Cloud Run

```bash
# Build and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/vet-ultrasound-api

gcloud run deploy vet-ultrasound-api \
  --image gcr.io/$PROJECT_ID/vet-ultrasound-api \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET_UPLOADS=${PROJECT_ID}-ultrasound-uploads,GCS_BUCKET_IMAGES=${PROJECT_ID}-ultrasound-images,DOCUMENTAI_PROCESSOR_ID=your-processor-id"
```

## Authentication

The API supports two authentication methods:

### API Key (Recommended for server-to-server)

```bash
curl -X POST https://your-api-url/api/v1/documents \
  -H "X-API-Key: your-api-key" \
  -F "file=@report.pdf"
```

### Bearer Token (For user-facing apps)

```bash
curl -X POST https://your-api-url/api/v1/documents \
  -H "Authorization: Bearer your-jwt-token" \
  -F "file=@report.pdf"
```

## Response Examples

### Upload Response (202 Accepted)

```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "uploading",
  "message": "Document uploaded successfully. Processing will begin shortly."
}
```

### Document Details (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "owner_id": "user-123",
  "status": "completed",
  "extracted_data": {
    "patient": {
      "name": "Max",
      "species": "Canino",
      "breed": "Golden Retriever",
      "age": "5 años",
      "weight": "32 kg"
    },
    "owner": {
      "name": "Juan García",
      "phone": "+52 55 1234 5678",
      "email": "juan@email.com"
    },
    "veterinarian": {
      "name": "Dra. María López",
      "license_number": "CEDULA-12345",
      "clinic_name": "VetCare Clinic"
    },
    "diagnosis": {
      "primary": "Hepatomegalia leve",
      "findings": [
        "Hígado con dimensiones ligeramente aumentadas",
        "Ecogenicidad normal",
        "Sin masas ni lesiones focales"
      ],
      "severity": "mild"
    },
    "recommendations": [
      {
        "type": "followup",
        "description": "Control ecográfico en 3 meses",
        "priority": "medium"
      },
      {
        "type": "medication",
        "description": "Hepatoprotector 1 tableta cada 12 horas",
        "priority": "medium"
      }
    ]
  },
  "images": [
    {
      "id": "img-001",
      "page_number": 2,
      "width": 800,
      "height": 600,
      "signed_url": "https://storage.googleapis.com/..."
    }
  ],
  "confidence_score": 0.92,
  "processing_time_ms": 3450,
  "created_at": "2026-02-03T10:30:00Z",
  "processed_at": "2026-02-03T10:30:03Z"
}
```

## Security Features

- **TLS Encryption**: All traffic encrypted in transit
- **API Key Hashing**: Keys stored as SHA-256 hashes
- **Rate Limiting**: 100 requests per minute per client
- **File Validation**: Magic byte verification + PDF structure validation
- **Signed URLs**: Time-limited access to stored files (1 hour expiry)
- **Ownership Verification**: Users can only access their own documents

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Project Structure

```
vet-ultrasound-api/
├── src/
│   ├── api/
│   │   ├── middleware/
│   │   │   ├── auth.py         # Authentication logic
│   │   │   └── rate_limiter.py # Rate limiting
│   │   └── routes/
│   │       ├── documents.py    # Document endpoints
│   │       └── health.py       # Health check
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   ├── services/
│   │   ├── document_ai.py      # Document AI integration
│   │   ├── firestore.py        # Database operations
│   │   ├── pdf_processor.py    # PDF/image extraction
│   │   └── storage.py          # Cloud Storage operations
│   ├── config.py               # Settings management
│   └── main.py                 # FastAPI application
├── tests/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Cost Estimation

For 10,000 PDFs/month:

| Service | Estimated Cost |
|---------|----------------|
| Cloud Run | ~$15/month |
| Cloud Storage | ~$5/month |
| Document AI | ~$15/month |
| Firestore | ~$5/month |
| **Total** | **~$40/month** |

## Known Limitations

- Document AI works best with clearly formatted PDFs. Handwritten notes may not extract properly.
- Currently supports Spanish and English field labels. Other languages need pattern updates in `document_ai.py`.
- Large PDFs (>50MB) are rejected to keep processing times reasonable.

## Future Improvements

- [ ] Add webhook notifications when processing completes
- [ ] Support batch upload for multiple PDFs
- [ ] Add PDF preview generation
- [ ] Implement caching with Redis for frequently accessed documents

## License

MIT License - see LICENSE file for details.

## Author

Built by Santiago García as part of a backend engineering challenge. Feel free to reach out with questions or suggestions!
