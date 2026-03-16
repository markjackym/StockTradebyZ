"""
llm_review.py
~~~~~~~~~~~~~
使用任意 OpenAI 兼容 API 对候选股票进行图表分析评分。
继承自 BaseReviewer 基础架构。

支持的 API 提供商（只要兼容 OpenAI Chat Completions 格式即可）：
  - OpenAI (GPT-4o 等)
  - Google Gemini (通过 OpenAI 兼容端点)
  - Deepseek
  - 阿里通义千问 (Qwen)
  - 智谱 GLM
  - Moonshot (Kimi)
  - 本地部署 (Ollama, vLLM, LMStudio 等)
  - 任何其他 OpenAI 兼容 API

用法：
    python agent/llm_review.py
    python agent/llm_review.py --config config/llm_review.yaml

配置：
    默认读取 config/llm_review.yaml。

环境变量：
    由配置文件中 api_key_env 指定（默认 LLM_API_KEY）

输出：
    ./data/review/{pick_date}/{code}.json   每支股票的评分 JSON
    ./data/review/{pick_date}/suggestion.json  汇总推荐建议
"""

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI
import yaml

from base_reviewer import BaseReviewer

# ────────────────────────────────────────────────
# 配置加载
# ────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "llm_review.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    # 路径参数（相对路径默认基于项目根目录）
    "candidates": "data/candidates/candidates_latest.json",
    "kline_dir": "data/kline",
    "output_dir": "data/review",
    "prompt_path": "agent/prompt.md",
    # API 参数
    "api_base": "https://api.openai.com/v1",
    "api_key_env": "LLM_API_KEY",
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 4096,
    # 运行参数
    "request_delay": 5,
    "skip_existing": False,
    "suggest_min_score": 4.0,
}


def _resolve_cfg_path(path_like: str | Path, base_dir: Path = _ROOT) -> Path:
    p = Path(path_like)
    return p if p.is_absolute() else (base_dir / p)


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    cfg_path = config_path or _DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到配置文件：{cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    cfg = {**DEFAULT_CONFIG, **raw}

    # 环境变量覆盖（Docker / CI 场景下优先级最高）
    if os.environ.get("LLM_API_BASE"):
        cfg["api_base"] = os.environ["LLM_API_BASE"]
    if os.environ.get("LLM_API_KEY"):
        cfg["api_key"] = os.environ["LLM_API_KEY"]
    if os.environ.get("LLM_MODEL"):
        cfg["model"] = os.environ["LLM_MODEL"]

    # BaseReviewer 依赖这些路径字段为 Path 对象
    cfg["candidates"] = _resolve_cfg_path(cfg["candidates"])
    cfg["kline_dir"] = _resolve_cfg_path(cfg["kline_dir"])
    cfg["output_dir"] = _resolve_cfg_path(cfg["output_dir"])
    cfg["prompt_path"] = _resolve_cfg_path(cfg["prompt_path"])

    return cfg


def _image_to_base64_url(path: Path) -> str:
    """将图片文件转为 base64 data URL，用于 OpenAI Vision API。"""
    suffix = path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    mime_type = mime_map.get(suffix, "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{data}"


class LLMReviewer(BaseReviewer):
    def __init__(self, config):
        super().__init__(config)

        # 优先从配置文件读取 api_key，其次从环境变量读取
        api_key = config.get("api_key", "")
        if not api_key:
            api_key_env = config.get("api_key_env", "LLM_API_KEY")
            api_key = os.environ.get(api_key_env, "")
        if not api_key:
            print(
                "[ERROR] 未找到 API Key，请在配置文件中设置 api_key，或设置环境变量。",
                file=sys.stderr,
            )
            sys.exit(1)

        self.client = OpenAI(
            api_key=api_key,
            base_url=config.get("api_base", "https://api.openai.com/v1"),
            default_headers={"User-Agent": "Mozilla/5.0"},
            http_client=httpx.Client(
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            ),
        )

    def review_stock(self, code: str, day_chart: Path, prompt: str) -> dict:
        """
        调用 OpenAI 兼容 API，对单支股票进行图表分析，返回解析后的 JSON 结果。
        """
        user_text = (
            f"股票代码：{code}\n\n"
            "以下是该股票的 **日线图**，请按照系统提示中的框架进行分析，"
            "并严格按照要求输出 JSON。"
        )

        image_url = _image_to_base64_url(day_chart)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "【日线图】"},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ]

        response = self.client.chat.completions.create(
            model=self.config.get("model", "gpt-4o"),
            messages=messages,
            temperature=self.config.get("temperature", 0.2),
            max_tokens=self.config.get("max_tokens", 4096),
        )

        response_text = response.choices[0].message.content
        if response_text is None:
            raise RuntimeError(f"API 返回空响应，无法解析 JSON（code={code}）")

        result = self.extract_json(response_text)
        result["code"] = code  # 附加股票代码便于追溯
        return result


def main():
    parser = argparse.ArgumentParser(description="LLM 图表复评（支持任意 OpenAI 兼容 API）")
    parser.add_argument(
        "--config",
        default=str(_DEFAULT_CONFIG_PATH),
        help="配置文件路径（默认 config/llm_review.yaml）",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config))

    print(f"[INFO] API: {config.get('api_base')}")
    print(f"[INFO] 模型: {config.get('model')}")

    reviewer = LLMReviewer(config)
    reviewer.run()


if __name__ == "__main__":
    main()
