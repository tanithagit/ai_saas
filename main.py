from fastapi import FastAPI

app = FastAPI(
    title="AI SaaS Backend",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/version")
def version():
    return {"version": app.version}