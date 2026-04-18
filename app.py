import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Ensure the project root is in PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.graph import run_procurement_workflow

app = FastAPI(title="Multi-Agent Procurement API", version="1.0.0")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    input: str


class RunResponse(BaseModel):
    result: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]]
    state: Dict[str, Any]


def run_mas(user_input: str) -> dict:
    """
    Wrapper around the internal state graph.
    Returns the final state after graph execution.
    """
    try:
        final_state = run_procurement_workflow(user_request=user_input)
        return final_state
    except Exception as e:
        raise Exception(f"MAS Execution Failed: {str(e)}")


@app.post("/run", response_model=RunResponse)
async def run_workflow(request: RunRequest):
    """
    Executes the Multi-Agent System on the provided text input.
    """
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")
    
    try:
        final_state = run_mas(request.input)
        
        # Decide the 'final' result based on the last agent's state updates
        final_result = None
        if final_state.get("approval_status"):
            final_result = final_state["approval_status"]
        elif final_state.get("purchase_order"):
            final_result = final_state["purchase_order"]
        elif final_state.get("selected_supplier"):
            final_result = final_state["selected_supplier"]
        elif final_state.get("parsed_request"):
            final_result = final_state["parsed_request"]

        # If there's an explicit error string in the state, append it to logs or return it
        if final_state.get("error"):
            # The execution short-circuited. We will still return the state and logs.
            pass

        return RunResponse(
            result=final_result,
            logs=final_state.get("logs", []),
            state=final_state
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
