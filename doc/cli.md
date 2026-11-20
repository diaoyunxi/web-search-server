> [← 返回文档目录](../README.md)

# 命令行参数与环境变量（`web_search_server.py`）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1`（环境变量 `SEARCH_SERVER_HOST`） | 绑定地址，仅本机访问 |
| `--port` | `8000`（环境变量 `SEARCH_SERVER_PORT`） | 监听端口 |
| `--api-key` | `DEEPSEEK_API_KEY` | API 密钥，空则不校验 |
| `--cors-origin` | `*`（环境变量 `SEARCH_SERVER_CORS_ORIGIN`） | `Access-Control-Allow-Origin` |

代码实际读取的环境变量只有以上四个（见 `web_search_server.py` 顶部常量与
`argparse` 默认值）。README 早期版本提到的 `USE_MOCK_RESULTS`、`SEARCH_API_KEY`、
`SEARCH_ENGINE`、`GOOGLE_CX`、`--no-mock` 以及多引擎切换，在代码中均不存在，已移除。

真实搜索实现：`_perform_real_search()` → DuckDuckGo HTML（`html.duckduckgo.com/html/`），
按 `result` 结果块解析 `result__a` / `result__snippet`；失败时由
`_build_search_response()` 返回失败提示，不产生模拟结果。
