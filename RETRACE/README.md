# RETRACE — Developer Diagnostics Prototype

RETRACE is a local prototype for reviewing recorded execution traces, locating the first failure signal, and inspecting evidence from each stage. The included purchase/order flow is a sample workload that produces trace events; it is not the product's main purpose.

## Prerequisites
- Python 3.11+ (the original project was developed with Python 3.13)
- PostgreSQL running locally
- A database named `retrace_db`

## Backend setup (Windows PowerShell)
```powershell
cd RETRACE\backend
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `backend\.env` and set `RETRACE_DB_PASSWORD` to your local PostgreSQL password. Do not commit or share `.env`.

Start the API:
```powershell
uvicorn main:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Frontend
In a second PowerShell terminal:
```powershell
cd RETRACE\frontend
py -m http.server 5500
```
Open http://127.0.0.1:5500

The frontend calls the local API at `http://127.0.0.1:8000`. Keep the backend terminal running while using it.

## Example input
`Buy 2 laptops for Rs. 50000`

The page shows the trace status, execution timeline, event details, integrity status, and the first recorded failure signal when one exists. This is evidence-based triage, not guaranteed automated identification of the underlying code defect.

## Existing project tests
With the backend virtual environment active and PostgreSQL configured:
```powershell
pytest
```

## Security note
This ZIP intentionally excludes local `.env` credentials, virtual environments, caches, and compiled Python files. Configure your own local environment before running.
