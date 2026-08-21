#!/usr/bin/env python3
"""
Anthropic Messages API 兼容的搜索服务器

这是一个简单的本地搜索服务器，用于测试 deepseek-harness 的 web_search 功能。
它实现了 Anthropic Messages API 协议，支持 web_search_20250305 server tool。

启动方式:
    python3 web_search_server.py [--port 18923] [--api-key your-key]

环境变量:
    DEEPSEEK_API_KEY  - API 密钥（可选）
    SEARCH_SERVER_PORT - 端口号，默认 8000
    USE_MOCK_RESULTS  - 使用模拟结果（默认 true）
"""

import argparse
import json
import os
import re
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

# 默认配置
DEFAULT_PORT = 18923
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
USE_MOCK = os.environ.get("USE_MOCK_RESULTS", "true").lower() == "true"


class SearchRequestHandler(BaseHTTPRequestHandler):
    """处理搜索请求的 HTTP 处理器"""

    # 存储请求历史
    request_log: list[dict[str, Any]] = []
    log_lock = threading.Lock()

    def log_message(self, format: str, *args: Any) -> None:
        """覆盖默认日志输出"""
        print(f"[SearchServer] {args[0]}", file=sys.stderr, flush=True)

    def _send_json_response(self, status_code: int, data: dict[str, Any]) -> None:
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _check_auth(self) -> bool:
        """检查 API 密钥认证"""
        api_key = self.headers.get("X-Api-Key", "") or self.headers.get("Authorization", "").replace("Bearer ", "")
        required_key = getattr(self.server, "api_key", "")

        if not required_key:
            return True  # 未设置密钥时允许所有请求
        return api_key == required_key

    def do_OPTIONS(self) -> None:
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Api-Key, anthropic-version")
        self.end_headers()

    def do_GET(self) -> None:
        """处理 GET 请求"""
        if self.path == "/health" or self.path == "/":
            self._send_json_response(200, {
                "status": "ok",
                "service": "web-search-server",
                "version": "1.0.0",
                "supported_tools": ["web_search_20250305"]
            })
        elif self.path == "/log":
            with self.log_lock:
                self._send_json_response(200, {
                    "total_requests": len(self.request_log),
                    "requests": self.request_log[-20:]
                })
        elif self.path == "/stats":
            with self.log_lock:
                self._send_json_response(200, {
                    "total_requests": len(self.request_log),
                    "api_key_set": bool(getattr(self.server, "api_key", "")),
                    "endpoint": "/messages",
                    "use_mock": USE_MOCK
                })
        else:
            self._send_json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """处理 POST 请求"""
        if self.path != "/messages":
            self._send_json_response(404, {"error": "Not found"})
            return

        # 检查认证
        if not self._check_auth():
            self._send_json_response(401, {"error": "Unauthorized"})
            return

        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request_data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json_response(400, {"error": "Invalid JSON"})
            return

        # 记录请求
        with self.log_lock:
            self.request_log.append({
                "timestamp": time.time(),
                "method": "POST",
                "path": "/messages",
                "headers": dict(self.headers),
                "body": request_data
            })

        # 处理请求
        try:
            response = self._handle_search_request(request_data)
            self._send_json_response(200, response)
        except Exception as e:
            print(f"[SearchServer] Error handling request: {e}", file=sys.stderr, flush=True)
            self._send_json_response(500, {"error": str(e)})

    def _handle_search_request(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """处理搜索请求"""
        messages = request_data.get("messages", [])
        tools = request_data.get("tools", [])
        model = request_data.get("model", "unknown")

        # 检查是否有 web_search tool
        search_tool = None
        for tool in tools:
            if tool.get("type") == "web_search_20250305":
                search_tool = tool
                break

        if not search_tool:
            return {
                "id": f"msg_{int(time.time())}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "No web search tool configured."}],
                "model": model,
                "stop_reason": "end_turn",
                "stop_sequence": None
            }

        # 提取搜索查询
        query = self._extract_query(messages)
        if not query:
            query = "test"

        # 执行搜索
        max_uses = search_tool.get("max_uses", 5)
        
        if USE_MOCK:
            results = self._generate_mock_results(query, max_uses)
        else:
            results = self._perform_real_search(query, max_uses)

        # 构建响应
        return self._build_search_response(results, query)

    def _extract_query(self, messages: list) -> str:
        """从消息中提取搜索查询"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, str):
                    match = re.search(r"Perform a web search for the query: (.+)", content)
                    if match:
                        return match.group(1)
                    return content
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text = item.get("text", "")
                            match = re.search(r"Perform a web search for the query: (.+)", text)
                            if match:
                                return match.group(1)
                            return text
        return ""

    def _perform_real_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """执行真实搜索（使用 DuckDuckGo）"""
        try:
            import urllib.request
            import urllib.parse
            
            encoded_query = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html"
                }
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                html = response.read().decode("utf-8", errors="ignore")
            
            results = []
            # 解析搜索结果
            link_pattern = r'<a class="result__a" href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
            snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
            
            links = re.findall(link_pattern, html)
            snippets = re.findall(snippet_pattern, html)
            
            for i, (link, title) in enumerate(links[:max_results]):
                link = re.sub(r"uddg=([^&]+).*", r"\1", link)
                link = urllib.parse.unquote(link)
                snippet = snippets[i] if i < len(snippets) else ""
                
                results.append({
                    "url": link,
                    "title": title.strip(),
                    "snippet": snippet.strip(),
                    "page_age": None
                })
            
            return results
            
        except Exception as e:
            print(f"[SearchServer] Real search failed: {e}", file=sys.stderr, flush=True)
            return self._generate_mock_results(query, max_results)

    def _generate_mock_results(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """生成模拟搜索结果"""
        mock_data = [
            ("https://docs.python.org/3/tutorial/", "Python Tutorial", "Learn Python, the hard way. This is a tutorial about Python."),
            ("https://wiki.python.org/moin/BeginnersGuide", "BeginnersGuide - Python Wiki", "Python wiki for beginners. Learn the basics of Python programming."),
            ("https://realpython.com/start-here/", "Start Here - Real Python", "A comprehensive guide to getting started with Python programming."),
            ("https://learnpython.org/", "Learn Python Interactively", "Free interactive Python tutorials for beginners and experts."),
            ("https://www.python.org/about/gettingstarted/", "Python Getting Started", "Official Python documentation for getting started."),
        ]
        
        results = []
        for i in range(min(max_results, len(mock_data))):
            url, title, snippet = mock_data[i]
            results.append({
                "url": url,
                "title": title,
                "snippet": snippet,
                "page_age": "2026-01-01" if i % 2 == 0 else None
            })
        
        return results

    def _build_search_response(self, results: list[dict[str, Any]], query: str) -> dict[str, Any]:
        """构建 Anthropic Messages API 格式的响应"""
        # 构建 citations
        citations = []
        for result in results:
            citations.append({
                "type": "web_search_result_location",
                "url": result["url"],
                "cited_text": result.get("snippet", "")[:200]
            })
        
        # 构建搜索结果 block
        search_results = []
        for result in results:
            item: dict[str, Any] = {
                "type": "web_search_result",
                "url": result["url"],
            }
            if result.get("title"):
                item["title"] = result["title"]
            if result.get("page_age"):
                item["page_age"] = result["page_age"]
            search_results.append(item)
        
        # 构建完整响应
        response = {
            "id": f"msg_{int(time.time())}",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(results)} sources for '{query}'.",
                    "citations": citations
                },
                {
                    "type": "web_search_tool_result",
                    "content": search_results
                }
            ],
            "model": "web-search-server",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": len(query.split()),
                "output_tokens": len(citations)
            }
        }
        
        return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic-compatible Web Search Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--api-key", type=str, default=None, help="API key for authentication")
    parser.add_argument("--no-mock", action="store_true", help="Disable mock results and use real search")
    args = parser.parse_args()

    port = args.port
    api_key = args.api_key or DEFAULT_API_KEY
    
    if args.no_mock:
        global USE_MOCK
        USE_MOCK = False

    server = HTTPServer(("0.0.0.0", port), SearchRequestHandler)
    server.api_key = api_key

    print(f"[SearchServer] Starting on http://0.0.0.0:{port}", flush=True)
    print(f"[SearchServer] API key {'set' if api_key else 'not set'}", flush=True)
    print(f"[SearchServer] Mock results: {USE_MOCK}", flush=True)
    print(f"[SearchServer] Endpoints:", flush=True)
    print(f"  POST /messages  - Search endpoint (Anthropic Messages API)", flush=True)
    print(f"  GET  /health    - Health check", flush=True)
    print(f"  GET  /log       - Request log", flush=True)
    print(f"  GET  /stats     - Server stats", flush=True)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SearchServer] Stopped", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
