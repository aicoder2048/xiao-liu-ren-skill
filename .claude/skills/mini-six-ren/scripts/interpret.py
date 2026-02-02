# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pydantic-ai-slim[openai,anthropic,google]>=0.2.0",
#     "python-dotenv>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""小六壬 AI 解读 - 使用 Pydantic AI 调用第三方 LLM

Usage:
    # 管道输入（从 xiaoliu.py JSON 输出）
    uv run scripts/xiaoliu.py --now --question "测试" --format json | \
      uv run scripts/interpret.py --question "测试"

    # 文件输入
    uv run scripts/interpret.py --prediction @result.json --question "测试"

    # 直接参数
    uv run scripts/interpret.py --prediction '{"passes": [...]}' --question "测试"

    # 指定模型（覆盖 config.yaml）
    uv run scripts/interpret.py --question "测试" --model deepseek:deepseek-chat
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ===== 提供商配置 =====

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    },
    "kimi": {
        "env_key": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.ai/v1",
    },
    "qwen": {
        "env_key": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "glm": {
        "env_key": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
    },
    "google-gla": {
        "env_key": "GEMINI_API_KEY",
    },
}

SYSTEM_PROMPT = """\
你是一位精通小六壬的占卜大师，深谙中华传统文化与术数智慧。请根据占卜结果，为用户提供深入解读。

## 解读结构

1. **卦象总览**: 概述三传符号及其五行属性
2. **时间发展脉络**:
   - 初传（前期/当前）: 该符号对此问题的含义
   - 中传（中期/发展）: 中间符号如何驱动变化
   - 末传（后期/结果）: 最终符号的预测
3. **五行生克解读**: 解释五行关系如何影响结果
4. **具体建议**: 与问题相关的实际可行建议
5. **关键提示**: 值得注意的方位、时机或神灵影响

## 解读要求

- 始终将解读与用户的具体问题联系起来
- 以末传（最终符号）作为最重要的指标
- 用通俗易懂的方式解释五行生克关系
- 解读控制在 800 字以内，简明扼要
- 使用优雅、富有哲理的中文，但保持易懂
"""


def resolve_model(model_str: str) -> tuple:
    """解析 'provider:model_name' 字符串，返回 (pydantic_ai_model, env_key)。

    对于国产模型（deepseek, kimi, qwen, glm），使用 OpenAI 兼容接口 + base_url。
    对于原生提供商（openai, anthropic, google-gla），使用 Pydantic AI 原生格式。
    """
    if ":" not in model_str:
        raise ValueError(
            f"模型格式错误: '{model_str}'。请使用 'provider:model_name' 格式，"
            f"例如 'deepseek:deepseek-chat'"
        )

    provider, model_name = model_str.split(":", 1)
    provider = provider.lower()

    if provider not in PROVIDER_CONFIG:
        supported = ", ".join(sorted(PROVIDER_CONFIG.keys()))
        raise ValueError(f"不支持的提供商: '{provider}'。支持的提供商: {supported}")

    config = PROVIDER_CONFIG[provider]
    env_key = config["env_key"]
    api_key = os.environ.get(env_key)

    if not api_key:
        raise EnvironmentError(f"未找到 API Key。请在 .env 文件中设置 {env_key}=sk-...")

    base_url = config.get("base_url")

    if base_url:
        # 国产模型：使用 OpenAI 兼容接口
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        model = OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key),
        )
    elif provider == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel

        model = AnthropicModel(model_name)
    elif provider == "google-gla":
        from pydantic_ai.models.google import GoogleModel

        model = GoogleModel(model_name)
    else:
        # openai 原生
        from pydantic_ai.models.openai import OpenAIChatModel

        model = OpenAIChatModel(model_name)

    return model, env_key


def interpret(prediction_json: str, question: str, model_str: str) -> str:
    """调用 Pydantic AI Agent 解读占卜结果。"""
    from pydantic_ai import Agent

    model, _ = resolve_model(model_str)
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT)

    user_prompt = f"## 用户问题\n\n{question}\n\n## 占卜结果（JSON）\n\n```json\n{prediction_json}\n```"

    result = agent.run_sync(user_prompt)
    return result.output


def load_prediction(source: str | None) -> str:
    """从各种来源加载占卜 JSON。

    - None: 从 stdin 读取
    - '@filename': 从文件读取
    - 其他: 视为 JSON 字符串
    """
    if source is None:
        if sys.stdin.isatty():
            print(
                "错误: 未提供占卜数据。请通过管道或 --prediction 参数传入。",
                file=sys.stderr,
            )
            sys.exit(1)
        return sys.stdin.read()

    if source.startswith("@"):
        filepath = Path(source[1:])
        if not filepath.exists():
            print(f"错误: 文件不存在: {filepath}", file=sys.stderr)
            sys.exit(1)
        return filepath.read_text(encoding="utf-8")

    return source


def load_config() -> dict:
    """加载 config.yaml（如果存在）。"""
    import yaml

    # 相对于脚本所在目录的上级（即 skill 根目录）
    skill_dir = Path(__file__).resolve().parent.parent
    config_path = skill_dir / "config.yaml"
    if config_path.exists():
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="小六壬 AI 解读 - Pydantic AI 第三方模型"
    )
    parser.add_argument(
        "--prediction",
        "-p",
        help="占卜结果 JSON（字符串 / @文件路径），不提供则从 stdin 读取",
    )
    parser.add_argument("--question", "-q", required=True, help="求问事项")
    parser.add_argument(
        "--model",
        "-m",
        help="模型 (provider:model_name)，覆盖 config.yaml",
    )
    args = parser.parse_args()

    # 加载 .env
    skill_dir = Path(__file__).resolve().parent.parent
    load_dotenv(skill_dir / ".env")

    # 确定模型
    model_str = args.model
    if not model_str:
        config = load_config()
        model_str = config.get("model")

    if not model_str:
        print(
            "错误: 未指定模型。请通过 --model 参数或 config.yaml 配置。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 加载占卜数据
    prediction_json = load_prediction(args.prediction)

    # 验证 JSON 格式
    try:
        json.loads(prediction_json)
    except json.JSONDecodeError as e:
        print(f"错误: 占卜数据不是有效的 JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # 解读
    print(f"ℹ️  当前使用 {model_str} 解读...", file=sys.stderr)
    try:
        analysis = interpret(prediction_json, args.question, model_str)
        print(analysis)
    except EnvironmentError as e:
        print(f"⚠️  {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误: AI 解读失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
