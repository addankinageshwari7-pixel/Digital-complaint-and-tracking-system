# Digital Complaint Management & Tracking System

Professional grievance redressal platform built with Flask + SQLite.

## Quick Start
```bash
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

## Default Admin
- Email: `admin@dcms.gov`
- Password: `admin123`

## Features
- Online complaint registration with unique IDs (CMP-YYYY-NNNNNN)
- Real-time tracking by Complaint ID + Email
- PDF receipt with QR code
- Excel export
- Admin panel with status workflow
- Chart.js analytics dashboard

## Deploy (Render/Railway)
- Uses `Procfile` (gunicorn) + `runtime.txt` (Python 3.11.9)
- SQLite database auto-creates on first run with sample data
