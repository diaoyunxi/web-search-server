# Web Search Server

一个兼容 Anthropic Messages API 的本地搜索服务器，用于测试和开发 deepseek-harness 的 `web_search` 功能。

## 功能特性

- ✅ 完全兼容 Anthropic Messages API 格式
- ✅ 支持 `web_search_20250305` server tool
- ✅ 模拟搜索结果（默认）
- ✅ 真实搜索（DuckDuckGo、Serper、Exa、Google、Brave）
- ✅ API 密钥认证
- ✅ CORS 支持
- ✅ 请求日志和统计

## 快速开始

### 启动服务器（使用模拟数据）

```bash
# 基本启动
python3 web_search_server.py

# 指定端口
python3 web_search_server.py --port 8080

# 设置 API 密钥
python3 web_search_server.py --api-key my-secret-key
```

### 启动服务器（使用真实搜索）

```bash
# 使用 DuckDuckGo（无需 API key）
USE_MOCK_RESULTS=false python3 web_search_server.py --no-mock

# 使用 Serper.dev（Google Search API）
SEARCH_API_KEY=your-serper-key SEARCH_ENGINE=serper python3 web_search_server.py --no-mock

# 使用 Exa API
SEARCH_API_KEY=your-exa-key SEARCH_ENGINE=exa python3 web_search_server.py --no-mock

# 使用 Google Custom Search API
SEARCH_API_KEY=your-google-key SEARCH_ENGINE=google GOOGLE_CX=your-cx python3 web_search_server.py --no-mock

# 使用 Brave Search API
SEARCH_API_KEY=your-brave-key SEARCH_ENGINE=brave python3 web_search_server.py --no-mock
```

## API 端点

### POST /messages

搜索端点，接受 Anthropic Messages API 格式的请求。

**请求示例：**
```json
{
  "model": "deepseek-v4-flash",
  "max_tokens": 4096,
  "messages": [{
    "role": "user",
    "content": [{
      "type": "text",
      "text": "Perform a web search for the query: Python tutorial"
    }]
  }],
  "tools": [{
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5
  }]
}
```

**响应示例：**
```json
{
  "id": "msg_1234567890",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Found 3 sources for 'Python tutorial'.",
      "citations": [
        {
          "type": "web_search_result_location",
          "url": "https://docs.python.org/3/tutorial/",
          "cited_text": "Learn Python, the hard way."
        }
      ]
    },
    {
      "type": "web_search_tool_result",
      "content": [
        {
          "type": "web_search_result",
          "url": "https://docs.python.org/3/tutorial/",
          "title": "Python Tutorial",
          "page_age": "2026-01-01"
        }
      ]
    }
  ],
  "model": "web-search-server",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 2,
    "output_tokens": 3
  }
}
```

### GET /health

健康检查端点。

### GET /stats

服务器统计信息。

### GET /log

请求日志（最近 20 条）。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | API 密钥 | 空 |
| `SEARCH_SERVER_PORT` | 端口号 | 8000 |
| `USE_MOCK_RESULTS` | 使用模拟结果 | true |
| `SEARCH_API_KEY` | 搜索 API 密钥 | 空 |
| `SEARCH_ENGINE` | 搜索引擎 | duckduckgo |

支持的搜索引擎：
- `duckduckgo` - 无需 API key
- `serper` - Serper.dev (Google)
- `exa` - Exa AI
- `google` - Google Custom Search
- `brave` - Brave Search

## 与 deepseek-harness 集成

### 配置搜索提供商

在 `cordis.patch.yml` 或用户配置中：

```yaml
- id: web-search-deepseek
  name: '@deepseek-ai/dsh-web-search-deepseek'
  config:
    baseURL: http://localhost:8080  # 指向本地服务器
    apiKeyEnv: DEEPSEEK_API_KEY
```

或使用环境变量：

```bash
export DEEPSEEK_SEARCH_BASE_URL=http://localhost:8080
export DEEPSEEK_API_KEY=my-secret-key
```

### 测试流程

1. 启动搜索服务器：
   ```bash
   python3 web_search_server.py --port 18923
   ```

2. 配置 deepseek-harness 使用本地服务器：
   ```bash
   export DEEPSEEK_SEARCH_BASE_URL=http://127.0.0.1:18923
   ```

3. 运行测试或启动应用

## 响应格式说明

服务器返回符合 Anthropic Messages API 格式的响应：

- `content[0]`: 文本块，包含搜索结果摘要和 citations
- `content[1]`: `web_search_tool_result` 块，包含结构化搜索结果

每个搜索结果包含：
- `url`: 结果链接
- `title`: 页面标题
- `page_age`: 发布时间（可选）

每个 citation 包含：
- `url`: 对应结果的 URL
- `cited_text`: 页面摘录文本

## 开发说明

### 添加新的搜索引擎

在 `_perform_real_search` 方法中添加新的搜索实现，或在 `_search_<engine>` 方法中添加具体实现。

### 修改模拟数据

编辑 `_generate_mock_results` 方法中的 `mock_data` 列表。

## 许可证

MIT
