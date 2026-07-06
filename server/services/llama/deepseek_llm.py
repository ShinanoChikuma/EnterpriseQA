"""DeepSeek LLM 适配器 — 实现 LlamaIndex CustomLLM 接口"""
import json
import urllib.error
import urllib.request
from typing import Any, Generator

from llama_index.core.llms import CustomLLM
from llama_index.core.llms import CompletionResponse

from services.api_settings_service import load_api_settings


class DeepSeekLLM(CustomLLM):
    """通过 DeepSeek Chat API 提供 LLM 能力。

    自动读取 api_settings.json 中的 api_key 和 model 配置。
    """

    context_window: int = 64000
    num_output: int = 4096
    model_name: str = "deepseek-chat"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        settings = load_api_settings()
        api_key = (
            (settings.get("api_keys") or {}).get("deepseek", "").strip()
            or settings.get("api_key", "").strip()
        )
        if not api_key:
            raise ValueError("未配置 DeepSeek API 密钥")
        self._api_key = api_key
        self.model_name = settings.get("model", "deepseek-chat")

    @classmethod
    def class_name(cls) -> str:
        return "DeepSeekLLM"

    @property
    def metadata(self) -> dict:
        return {"model_name": self.model_name}

    def _call_api(self, messages: list[dict], temperature: float = 0.3) -> str:
        payload = json.dumps({
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }).encode("utf-8")

        request = urllib.request.Request(
            url="https://api.deepseek.com/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"DeepSeek 请求失败: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"DeepSeek 连接失败: {exc.reason}") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"DeepSeek 返回数据格式异常: {data}") from exc

    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        """同步补全 —— LlamaIndex 会把 RAG prompt 传到这里。"""
        temperature = kwargs.get("temperature", 0.3)
        answer = self._call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return CompletionResponse(text=answer)

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> Generator[CompletionResponse, None, None]:
        """流式补全 —— 当前项目不需要，直接走非流式。"""
        temperature = kwargs.get("temperature", 0.3)
        answer = self._call_api(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        yield CompletionResponse(text=answer, delta=answer)
