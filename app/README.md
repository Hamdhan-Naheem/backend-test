How to run the project

# Go to app folder

cd backend-test/app

# Create + activate virtual env

python -m venv venv# PowerShell.\venv\Scripts\Activate.ps1

# Install packages

pip install -r requirements.txt

# Set env variables

Create .env inside app/:
DATABASE_URL=postgresql://postgres:password@localhost:5432/Events
Make sure the Events database exists in Postgres.

# Setup Prisma (first time or after schema change)

prisma generateprisma migrate dev --name init

# Run the server

uvicorn main:app --reload
Open in browser:
http://127.0.0.1:8000/ – home (events list + featured)
http://127.0.0.1:8000/signup – create account
http://127.0.0.1:8000/login – login
http://127.0.0.1:8000/backend – backend (needs login)

Main things in the project
FastAPI
All routes are in
main.py
api/routes/

API routes
/api/auth/\_ – signup, signin, current user.
/api/events/ – events CRUD (list, get, create, update, delete).

HTML pages:
/ – events list + featured.
/events/{id} – detail + Twitter share.
/login, /signup – forms.
/backend/... – admin area (list + create/edit/delete events).

Auth & JWT
Passwords hashed in core/security.py.
JWT tokens created there too.
Token is stored in a cookie for HTML and as JSON for API.
Protected routes check the token in api/deps.py.

Backend section
Only logged-in users can access /backend.
You can:
See all events (paginated).
Create new event.
Edit existing event.
Delete event.

# Prisma (short explanation)

Schema file: app/prisma/schema.prisma
Models:
User – id, email, password hash, created/updated times.
Event – title, description, location, image url, featured, dates.
EventDate – one row per event date (supports list of dates).

    Prisma Commands:
        prisma generate
        Reads schema.prisma and generates the Python client used in database.py.
        prisma migrate dev --name init
        Creates/updates tables in Postgres and stores SQL in prisma/migrations/.
