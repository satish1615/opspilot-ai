OpsPilot AI - Sprint 0 Notes
Goal: Create the basic FastAPI backend foundation and confirm that it runs successfully.
What We Built
- Created the project folder structure.
- Created and activated a Python virtual environment.
- Installed FastAPI and Uvicorn.
- Added home and health-check endpoints.
- Tested the API locally and opened Swagger documentation.
Project Structure
opspilot-ai/
|-- app/ Backend code
|-- dashboard/ Future user interface
|-- data/ Local data and database
|-- docs/ Sprint notes and preparation
|-- tests/ Automated tests
|-- requirements.txt
|-- README.md
|-- .gitignore
Main Commands
Command Purpose
mkdir opspilot-ai && cd opspilot-ai Create and enter the project folder.
python3 -m venv venv Create an isolated Python environment.
source venv/bin/activate Activate the virtual environment.
pip install -r requirements.txt Install project dependencies.
uvicorn app.main:app --reload Start the FastAPI development server.
requirements.txt
fastapi
uvicorn[standard]
This file lists the Python packages required by the project so the environment can be recreated on another machine.
main.py
from fastapi import FastAPI
app = FastAPI(
title="OpsPilot AI",
description="AI-powered incident investigation and remediation platform",
version="0.1.0",
)
@app.get("/")
def home():
return {"message": "OpsPilot AI backend is running"}
@app.get("/health")
def health_check():
return {"status": "healthy"}
Key Concepts
Term Meaning
FastAPI Python framework used to build backend APIs.
Uvicorn Server that runs the FastAPI application.
Endpoint A URL that performs a specific API operation, such as /health.
GET HTTP method used to retrieve data.
JSON Standard format used to exchange data between applications.
Virtual environment Keeps this project's Python packages isolated.
127.0.0.1 The current computer, also called localhost.
Port 8000 The network port on which the backend is running.
Swagger UI Automatic interactive API documentation at /docs.
200 OK The request completed successfully.
Request Flow
Browser -> Uvicorn -> FastAPI endpoint -> Python function -> JSON response -> Browser
Useful URLs
Home: http://127.0.0.1:8000
Health check: http://127.0.0.1:8000/health
Swagger documentation: http://127.0.0.1:8000/docs
Important Notes
- The application currently runs only on your Mac; it is not publicly deployed.
- The favicon.ico 404 message is harmless because no browser-tab icon has been added.
- The --reload option is useful during development but is normally avoided in production.
Judge Explanation
"In Sprint 0, we created the foundational FastAPI backend for OpsPilot AI. We configured an isolated Python
environment, added health-check endpoints, and enabled automatic API documentation. This backend will later
receive alerts and coordinate incident investigation and remediation."
Quick Interview Questions
Q: What is FastAPI?
A: A Python framework used to build APIs quickly.
Q: Why use a virtual environment?
A: To isolate dependencies and avoid conflicts.
Q: Why create /health?
A: To let monitoring systems check whether the service is available.
Q: What is Swagger UI?
A: Interactive documentation used to view and test API endpoints.
Q: What does 200 OK mean?
A: The request was completed successfully.
Sprint 0 Summary: We created and successfully ran the basic FastAPI backend that will act as the foundation of
OpsPilot AI.