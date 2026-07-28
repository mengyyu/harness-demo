# 🤖 Harness Framework

基于 **LangGraph + MCP + Mem0** 的 Agent 编排框架，支持 Agent Loop、Skill 调度、MCP 工具调用、三层记忆体系。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 一键演示（最快体验）
python run_demo.py --demo

# CLI 交互模式
python run_demo.py

# 启动 API + 管理后台
python run_demo.py --all
```

## 访问地址

| 服务 | 地址 |
|------|------|
| Streamlit 管理后台 | http://localhost:8501 |
| FastAPI Swagger | http://localhost:8000/docs |
| API 健康检查 | http://localhost:8000/health |

## 项目结构

```
harness-demo/
├── run_demo.py                  # 一键启动入口
├── harness/                     # 核心框架
│   ├── agent/loop.py            # Agent Loop (LangGraph: Plan→Execute→Observe→Reflect)
│   ├── skills/                  # Skill 基类 + 注册中心 + 导入导出
│   ├── mcp/manager.py           # MCP 协议管理器
│   ├── memory/store.py          # Mem0 风格三层记忆
│   ├── intent/router.py         # 意图路由器
│   └── tracker.py               # 执行追踪器
├── skills/                      # 内置 Skill 包
│   ├── report_parser/           # 基金诊断报告解析
│   └── summary_generator/       # 多源总结生成
├── mcp_servers/                 # MCP Server
│   └── demo_tools.py            # 演示工具（文档解析/账户分析/持仓查询）
├── api/main.py                  # FastAPI (18 个接口)
└── admin/app.py                 # Streamlit 管理后台
```

## 架构

```
用户输入 → 意图路由 → Agent Loop (Plan→Execute→Observe→Reflect)
                      ├── Skill 调度
                      ├── MCP Tool 调用
                      ├── Mem0 记忆检索
                      └── LangFuse 风格追踪
```

## 管理后台功能

- 📊 Dashboard — 运行统计、Skill 排行、意图分布
- 📝 Agent 运行 — 日志查看、步骤回放
- 🔧 Skill 管理 — 列表、导入导出 `.harness-skill`
- 🎯 意图库 — CRUD、在线测试路由
- 💬 对话测试 — Chat 交互验证
- 🧠 记忆管理 — 三层记忆浏览

## License

MIT
