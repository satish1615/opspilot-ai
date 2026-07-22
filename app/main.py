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