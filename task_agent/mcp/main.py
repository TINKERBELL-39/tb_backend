from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from client import GSuiteMCPClient

app = FastAPI(title="GSuite MCP Proxy API")

# MCP Client 인스턴스 (서버 시작 시 실행)
mcp_client = GSuiteMCPClient()

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict

@app.get("/tools")
def list_tools():
    """사용 가능한 MCP 툴 목록"""
    try:
        return {"tools": mcp_client.list_tools()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/call")
def call_tool(request: ToolCallRequest):
    """특정 MCP 툴 호출"""
    try:
        result = mcp_client.call_tool(request.tool_name, request.arguments)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
def shutdown_event():
    mcp_client.close()
