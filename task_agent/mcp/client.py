import json
import subprocess
from typing import Any, Dict, List, Optional


class GSuiteMCPClient:
    def __init__(self, node_path: str = "node", entry_script: str = "/Users/comet39/SKN_PJT/SKN11-FINAL-5Team/google-workspace-mcp-server/build/index.js"):
        """
        MCP 서버를 Node.js로 실행
        """
        self.proc = subprocess.Popen(
            [node_path, entry_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.request_id = 0

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        MCP 서버와 JSON-RPC 통신을 수행
        """
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("MCP 서버가 종료되었거나 연결이 끊어졌습니다.")

        response_line = self.proc.stdout.readline().strip()
        if not response_line:
            raise RuntimeError("MCP 서버 응답 없음")

        response = json.loads(response_line)
        if "error" in response:
            raise RuntimeError(f"MCP Error: {response['error']}")

        return response["result"]

    # def list_tools(self) -> List[Dict[str, Any]]:
    #     return self._send_request("listTools")

    # def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    #     return self._send_request("callTool", {"name": tool_name, "arguments": arguments})

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._send_request("list_tools")  # 기존 listTools → list_tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._send_request("call_tool", {"name": tool_name, "arguments": arguments})

    def close(self):
        if self.proc:
            self.proc.terminate()
