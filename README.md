# Spotter AI - Full Stack HOS Trip Planner

A full-stack, FMCSA Hours-of-Service (HOS) compliant truck trip planner built with **Django REST Framework** and **React (TypeScript + Leaflet)**.

## Architecture & Principles
- **One Deterministic Event Stream**: The map, timeline, and Driver's Daily Log sheets are rendered directly from a single canonical schedule calculated by a pure Python HOS engine.
- **HOS Rules (Property-Carrying 70h/8d)**:
  - 11-hour driving limit per shift
  - 14-hour consecutive driving window per shift
  - 30-minute break after 8 cumulative hours of driving
  - 10-hour consecutive off-duty reset
  - 70-hour / 8-day cycle limit with 34-hour restart
  - Fuel stops at least once every 1,000 miles
  - 1 hour pickup and 1 hour dropoff service events

## Repository Layout
```
├── backend/            # Django REST Framework API & Pure Python HOS engine
│   ├── config/         # Django project settings and URLs
│   └── planner/        # HOS scheduler, task builder, daily log generator & tests
├── frontend/           # React + TypeScript + Leaflet frontend
│   └── src/            # Components, map, SVG daily log grids, and state
└── README.md
```

## Setup & Running Locally

### Backend
1. `cd backend`
2. `python -m venv .venv`
3. Activate virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`
4. `pip install -r requirements.txt`
5. `python manage.py runserver`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`
