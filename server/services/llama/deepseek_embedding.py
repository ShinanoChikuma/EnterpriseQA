"""DeepSeek Embedding 适配器 — 实现 LlamaIndex BaseEmbedding 接口"""
import json
import urllib.error
import urllib.request
from typing import Any, List

from llama_index.core.embeddings import BaseEmbedding

from services.api_settings_service import load_api_settings


class DeepSeekEmbedding(BaseEmbedding):
    """通过 DeepSeek Embedding API 提供向量化能力。

    自动读取 api_settings.json 中的 api_key 和 embed_model 配置。
    LlamaIndex 自动处理批量化和重试，无需手工管理。
    """

    _api_key: str = ""
    _embed_model: str = "deepseek-embedding"

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
        self._embed_model = settings.get("embed_model", "deepseek-embedding")

    @classmethod
    def class_name(cls) -> str:
        return "DeepSeekEmbedding"

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """单次 API 调用，返回向量列表。"""
        payload = json.dumps({
            "model": self._embed_model,
            "input": texts,
        }).encode("utf-8")

        request = urllib.request.Request(
            url="https://api.deepseek.com/embeddings",
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
            raise RuntimeError(f"DeepSeek Embedding 请求失败: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek Embedding 连接失败: {exc.reason}") from exc

        try:
            return [item["embedding"] for item in data["data"]]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"DeepSeek Embedding 返回数据格式异常: {data}") from exc

    # ── LlamaIndex 要求的三个抽象方法 ──────────────────────

    def _get_text_embedding(self, text: str) -> List[float]:
        embeddings = self._call_api([text])
        return embeddings[0]

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        """异步版 —— 当前项目同步运行，直接复用同步实现。"""
        return self._get_text_embedding(query)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化 —— 覆写以利用 DeepSeek 原生批量 API。"""
        return self._call_api(texts)
