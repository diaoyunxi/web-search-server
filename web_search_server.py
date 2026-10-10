#!/usr/bin/env python3
"""
Anthropic Messages API 兼容的搜索服务器

这是一个简单的本地搜索服务器，用于测试 deepseek-harness 的 web_search 功能。
它实现了 Anthropic Messages API 协议，支持 web_search_20250305 server tool。

启动方式:
    python3 web_search_server.py [--host 127.0.0.1] [--port 18923] [--api-key your-key]

环境变量:
    DEEPSEEK_API_KEY  - API 密钥（可选）
    SEARCH_SERVER_HOST - 绑定地址，默认 127.0.0.1（仅本机访问）
    SEARCH_SERVER_PORT - 端口号，默认 8000
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
                    "endpoint": "/messages"
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
        results = self._perform_real_search(query, max_uses)

        # 构建响应
        return self._build_search_response(results, query)

    def _extract_query(self, messages: list) -> str:
        """从消息中提取搜索查询（反向遍历取最近用户消息）"""
        for msg in reversed(messages):
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
            # 解析搜索结果 — 以整个结果块为单位提取，避免链接/摘要索引错位
            # DuckDuckGo HTML 版每个搜索结果是一个 class="result" 的 div，
            # 内部包含 result__a (标题链接) 和 result__snippet (摘要)。
            # 旧实现分两次独立正则匹配链接和摘要再按下标配对，当 HTML 结构
            # 变化（如某个结果缺少摘要或出现额外 result__a）时会导致索引不对齐。
            result_block_pattern = re.compile(
                r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="[^"]*result|$)',
                re.DOTALL
            )
            link_re = re.compile(
                r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            snippet_re = re.compile(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
                re.DOTALL
            )
            tag_re = re.compile(r'<[^>]+>')

            blocks = result_block_pattern.findall(html)

            # 如果按块提取无结果，回退到宽松模式：在整个 HTML 上逐条匹配
            if not blocks:
                blocks = [html]

            for block in blocks:
                if len(results) >= max_results:
                    break
                link_match = link_re.search(block)
                if not link_match:
                    continue
                raw_href = link_match.group(1)
                raw_title = link_match.group(2)

                # 从 DDG 重定向链接 /l/?uddg=URL&... 中提取真实 URL
                actual_url = raw_href
                parsed_qs = urllib.parse.urlparse(raw_href).query
                if parsed_qs:
                    params = urllib.parse.parse_qs(parsed_qs)
                    uddg = params.get("uddg", [None])[0]
                    if uddg:
                        actual_url = urllib.parse.unquote(uddg)
                elif raw_href.startswith("/"):
                    # 相对路径但无 uddg 参数，丢弃
                    continue

                # 清理 HTML 标签和实体
                clean_title = tag_re.sub("", raw_title).strip()
                clean_title = clean_title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

                snippet_match = snippet_re.search(block)
                clean_snippet = ""
                if snippet_match:
                    clean_snippet = tag_re.sub("", snippet_match.group(1)).strip()
                    clean_snippet = clean_snippet.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')

                results.append({
                    "url": actual_url,
                    "title": clean_title,
                    "snippet": clean_snippet,
                    "page_age": None
                })
            
            return results
            
        except Exception as e:
            print(f"[SearchServer] Real search failed: {e}", file=sys.stderr, flush=True)
            return []

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
    parser.add_argument("--host", type=str, default=os.getenv("SEARCH_SERVER_HOST", "127.0.0.1"), help="Host to bind (default: 127.0.0.1, env: SEARCH_SERVER_HOST)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--api-key", type=str, default=None, help="API key for authentication")
    args = parser.parse_args()

    host = args.host
    port = args.port
    api_key = args.api_key or DEFAULT_API_KEY

    server = HTTPServer((host, port), SearchRequestHandler)
    server.api_key = api_key

    print(f"[SearchServer] Starting on http://{host}:{port}", flush=True)
    print(f"[SearchServer] API key {'set' if api_key else 'not set'}", flush=True)
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
