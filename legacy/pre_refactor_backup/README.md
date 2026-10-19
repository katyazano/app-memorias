# Construction Project Management Platform

A full-stack construction project management tool with an async SQLAlchemy/FastAPI backend, PostgreSQL database, and Streamlit testing dashboard.

---

## 🛠️ Tech Stack

- **Database**: PostgreSQL 16 (via Docker Compose)
- **ORM**: SQLAlchemy 2.0 (AsyncIO) & Asyncpg
- **Backend**: FastAPI & Pydantic V2
- **Storage / Parsing Bridge**: Boto3 (AWS S3) & OCR Parser Service
- **Testing Frontend**: Streamlit & Pandas
- **Package Manager**: Poetry

---

## 🚀 Getting Started

### 1. Start PostgreSQL with Docker Compose
```bash
docker compose up -d
```

### 2. Install Dependencies with Poetry
```bash
poetry install
```

### 3. Launch the FastAPI Backend
```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Interactive OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Launch the Streamlit Testing Dashboard
```bash
poetry run streamlit run streamlit_app.py
```
- Streamlit UI: [http://localhost:8501](http://localhost:8501)

---

## 📋 Features & Views

1. **Sidebar Navigation**:
   - Dynamic project selector synced globally via `st.session_state`.
   - Quick-creation modal if no projects exist yet.

2. **View 1: Upload Hub (PDF Parser Bridge)**:
   - Batch upload raw PDF invoices to AWS S3.
   - Run simulated/real OCR extraction.
   - Interactive `st.data_editor` to review & fix invoice data before saving to PostgreSQL.

3. **View 2: Manual Registry**:
   - **Payroll**: Disburse wages to registered workers.
   - **Bank Transfers**: Log direct wire payments.
   - **General Notes**: Log petty cash and incidental notes.

4. **View 3: Bi-Weekly Memory Generator**:
   - Select custom 14-day date ranges.
   - Aggregated metric cards (`Total Materials`, `Total Payroll`, `Combined Expenses`).
   - Detailed breakdown tables and report export button.
