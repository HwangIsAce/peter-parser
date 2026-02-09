"""Main entry point for Peter Parser API server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "peter_parser.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
