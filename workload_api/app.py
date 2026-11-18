from flask import Flask

app = Flask(__name__)
VERSION = "v2"


@app.get("/")
def index():
    return {"app": "workload-api", "version": VERSION}


@app.get("/healthz")
def health():
    return {"status": "ok"}