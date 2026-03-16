# StockTradebyZ

**量化初选 + LLM 图表复评** 的 A 股波段选股系统。

系统每日自动完成：拉取全市场 K 线 → 量化策略初选 → 导出候选股 K 线图 → 调用 LLM（GPT / Gemini / Deepseek 等）对图表做主观分析打分 → 输出最终推荐。

## 功能

- **量化初选** — KDJ + 知行均线多头排列（B1 策略）、砖型图策略等可配置规则
- **LLM 图表复评** — 将日线图发送给任意 OpenAI 兼容 API，由大模型做视觉分析评分
- **Streamlit 看板** — 交互式 K 线图（日线 / 周线），实时查看候选股票
- **一键全流程** — `run_all.py` 串联 fetch → preselect → export → review → 输出推荐

## 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
export TUSHARE_TOKEN=你的tushare_token     # https://tushare.pro/register
export LLM_API_KEY=sk-xxx                   # LLM API 密钥
export LLM_API_BASE=https://api.openai.com/v1
export LLM_MODEL=gpt-4o

# 3. 运行完整流程
python run_all.py

# 4. 启动看板
streamlit run dashboard/app.py
```

### Docker

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env 填入你的 Token 和 API Key

# 2. 启动看板（http://localhost:8501）
docker compose up dashboard

# 3. 运行完整选股流程
docker compose run --rm pipeline

# 4. 仅运行 LLM 评分
docker compose run --rm pipeline review
```

## 环境变量

| 变量 | 用途 | 必填 |
|---|---|---|
| `TUSHARE_TOKEN` | Tushare Pro API Token | 拉取行情时必填 |
| `LLM_API_KEY` | LLM API 密钥 | LLM 评分时必填 |
| `LLM_API_BASE` | API 地址（OpenAI 兼容） | 可选，默认 OpenAI |
| `LLM_MODEL` | 模型名称 | 可选，默认 gpt-4o |

环境变量优先级高于 `config/llm_review.yaml` 中的配置。

## 项目结构

```
├── run_all.py                  # 全流程入口
├── pipeline/
│   ├── fetch_kline.py          # 步骤1：拉取 K 线数据
│   ├── cli.py                  # 步骤2：量化初选 CLI
│   ├── select_stock.py         # 选股核心逻辑
│   └── ...
├── dashboard/
│   ├── app.py                  # Streamlit 看板主入口
│   ├── export_kline_charts.py  # 步骤3：批量导出 K 线图
│   └── components/             # 图表组件
├── agent/
│   ├── llm_review.py           # 步骤4：LLM 图表复评
│   ├── base_reviewer.py        # 评审基类
│   └── prompt.md               # LLM 系统提示词
├── config/                     # 各模块 YAML 配置
├── Dockerfile
├── docker-compose.yml
└── docker-entrypoint.sh
```

## 配置文件

- `config/fetch_kline.yaml` — 行情抓取：日期范围、排除板块、并发数
- `config/rules_preselect.yaml` — 量化选股规则参数
- `config/llm_review.yaml` — LLM API 配置、模型参数、路径
- `config/dashboard.yaml` — 看板图表参数

## 许可证

本项目基于 [SebastienZh/StockTradebyZ](https://github.com/SebastienZh/StockTradebyZ)，采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 协议发布。

仅供学习和个人使用，禁止商业用途。
