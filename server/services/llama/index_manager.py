"""知识库索引管理器 — 基于 LlamaIndex 的索引全生命周期管理。

替代旧的 VectorService + RAGService。
每个知识库 (kb_id) 对应一个独立持久化的 VectorStoreIndex。
"""
import csv
import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional, Tuple

from flask import current_app
from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import SimpleVectorStore

from services.llama.deepseek_embedding import DeepSeekEmbedding
from services.llama.deepseek_llm import DeepSeekLLM

# ── RAG 提示词（保持与原来一致） ──────────────────────────

SYSTEM_PROMPT = """你是一个企业内部知识库智能问答助手。请仅根据参考资料回答问题。

要求：
1. 只基于参考资料作答，不要编造信息。
2. 如果参考资料不足以回答，请明确说明。
3. 回答准确、简洁、专业。
4. 使用中文回答。

参考资料：
{context}
"""

# ── 从旧 VectorService 保留的 .doc 解析逻辑 ──────────────


def _read_text_file(file_path: str) -> str:
    """编码自适应的文本文件读取。"""
    with open(file_path, "rb") as file:
        raw = file.read()

    candidate_encodings = (
        "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be",
        "gb18030", "gbk", "big5", "shift_jis", "cp932", "euc_jp",
    )

    best_text = ""
    best_score = -1.0

    for encoding in candidate_encodings:
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        score = _score_decoded_text(decoded)
        if score > best_score:
            best_text = decoded
            best_score = score

    return best_text if best_text else raw.decode("utf-8", errors="ignore")


def _score_decoded_text(text: str) -> float:
    if not text:
        return float("-inf")
    valid_chars = sum(1 for c in text if c.isprintable() or c in "\r\n\t")
    printable_ratio = valid_chars / len(text)
    weird_penalty = sum(1 for c in text if ord(c) < 32 and c not in "\r\n\t")
    replacement_penalty = text.count("\ufffd")
    asian_bonus = sum(
        1 for c in text
        if "\u3040" <= c <= "\u30ff"
        or "\u4e00" <= c <= "\u9fff"
        or "\uff00" <= c <= "\uffef"
    )
    return printable_ratio * 1000 + asian_bonus - weird_penalty * 20 - replacement_penalty * 50


def _load_doc_text(file_path: str) -> str:
    """解析 .doc 文件，优先 Word COM，回退 LibreOffice。"""
    text = _load_doc_with_word(file_path)
    if text.strip():
        return text
    text = _load_doc_with_libreoffice(file_path)
    if text.strip():
        return text
    raise ValueError(
        "DOC 文件解析失败。请确认当前机器已安装 Microsoft Word 或 LibreOffice，"
        "并且已安装项目依赖中的 pywin32。"
    )


def _load_doc_with_word(file_path: str) -> str:
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return ""

    word = None
    document = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(file_path, ReadOnly=True)
        return document.Content.Text or ""
    except Exception:
        return ""
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _load_doc_with_libreoffice(file_path: str) -> str:
    soffice_path = shutil.which("soffice")
    if not soffice_path:
        return ""

    temp_dir = tempfile.mkdtemp(prefix="enterpriseqa-doc-")
    try:
        subprocess.run(
            [
                soffice_path, "--headless", "--convert-to", "txt:Text",
                "--outdir", temp_dir, file_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        txt_name = f"{os.path.splitext(os.path.basename(file_path))[0]}.txt"
        txt_path = os.path.join(temp_dir, txt_name)
        if not os.path.exists(txt_path):
            return ""
        return _read_text_file(txt_path)
    except Exception:
        return ""
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── .doc Reader ──────────────────────────────────────────

def _load_file_as_documents(
    file_path: str, file_type: str, doc_id: str, file_name: str
) -> List[Document]:
    """将任意格式文件解析为 LlamaIndex Document 列表。

    - 常见格式由 SimpleDirectoryReader 处理
    - .doc 格式使用 Word COM / LibreOffice 回退
    - 所有 Document 的 doc_id 设为数据库 doc_id（用于后续删除）
    """
    from llama_index.core import SimpleDirectoryReader

    if file_type == "doc":
        text = _load_doc_text(file_path)
        if not text.strip():
            raise ValueError("文档内容为空")
        return [Document(
            text=text,
            doc_id=doc_id,
            metadata={"file_name": file_name, "doc_id": doc_id},
        )]

    reader = SimpleDirectoryReader(
        input_files=[file_path],
    )
    documents = reader.load_data()

    # 注入自定义 doc_id 和元数据
    for doc in documents:
        doc.doc_id = doc_id
        doc.metadata["file_name"] = file_name
        doc.metadata["doc_id"] = doc_id

    if not documents:
        raise ValueError("文档内容为空，无法进行向量化")
    return documents


# ── CSRF 解析（保留，用于 CSV 格式支持） ──────────────────

def _load_csv_as_document(file_path: str, doc_id: str, file_name: str) -> List[Document]:
    """CSV 特殊处理：用 | 分隔符拼接每行。"""
    text = _read_text_file(file_path)
    rows = []
    reader = csv.reader(text.splitlines())
    for row in reader:
        cleaned = [cell.strip() for cell in row if str(cell).strip()]
        if cleaned:
            rows.append(" | ".join(cleaned))
    content = "\n".join(rows)
    if not content.strip():
        raise ValueError("CSV 内容为空")
    return [Document(
        text=content,
        doc_id=doc_id,
        metadata={"file_name": file_name, "doc_id": doc_id},
    )]


# ── XLSX 解析 ────────────────────────────────────────────

def _load_xlsx_as_documents(file_path: str, doc_id: str, file_name: str) -> List[Document]:
    """XLSX 特殊处理：逐工作表、逐行拼接。"""
    from openpyxl import load_workbook

    workbook = load_workbook(file_path, data_only=True, read_only=True)
    text_parts = []
    for sheet in workbook.worksheets:
        sheet_lines = [f"工作表: {sheet.title}"]
        for row in sheet.iter_rows(values_only=True):
            cleaned = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if cleaned:
                sheet_lines.append(" | ".join(cleaned))
        if len(sheet_lines) > 1:
            text_parts.append("\n".join(sheet_lines))
    workbook.close()

    content = "\n\n".join(text_parts)
    if not content.strip():
        raise ValueError("XLSX 内容为空")
    return [Document(
        text=content,
        doc_id=doc_id,
        metadata={"file_name": file_name, "doc_id": doc_id},
    )]


# ── RTF 解析 ─────────────────────────────────────────────

def _load_rtf_as_document(file_path: str, doc_id: str, file_name: str) -> List[Document]:
    """RTF 特殊处理。"""
    from striprtf.striprtf import rtf_to_text

    text = rtf_to_text(_read_text_file(file_path))
    if not text.strip():
        raise ValueError("RTF 内容为空")
    return [Document(
        text=text,
        doc_id=doc_id,
        metadata={"file_name": file_name, "doc_id": doc_id},
    )]


# ── 格式到解析函数的映射 ─────────────────────────────────

_LOADERS = {
    "csv": _load_csv_as_document,
    "xlsx": _load_xlsx_as_documents,
    "rtf": _load_rtf_as_document,
    "doc": _load_file_as_documents,  # doc 已在上面的通用函数中处理
}


def _load_documents(file_path: str, file_type: str, doc_id: str, file_name: str) -> List[Document]:
    """根据文件类型选择合适的解析器。"""
    file_type = (file_type or "").lower()

    # CSV / XLSX / RTF 用自定义解析器（保证输出格式一致）
    if file_type in _LOADERS:
        return _LOADERS[file_type](file_path, doc_id, file_name)

    # 其余格式统一用 SimpleDirectoryReader（支持 pdf, docx, epub, html, txt, md 等）
    return _load_file_as_documents(file_path, file_type, doc_id, file_name)


# ── IndexManager ─────────────────────────────────────────


class IndexManager:
    """知识库索引全生命周期管理。

    一个 IndexManager 实例管理所有知识库的索引。
    索引持久化路径: vector_data/kb_{kb_id}/
    """

    _sentence_splitter: Optional[SentenceSplitter] = None
    _embed_model: Optional[DeepSeekEmbedding] = None
    _llm: Optional[DeepSeekLLM] = None

    def __init__(self) -> None:
        self._base_dir = current_app.config["VECTOR_STORE_DIR"]
        self._splitter = SentenceSplitter(
            chunk_size=current_app.config.get("CHUNK_SIZE", 500),
            chunk_overlap=current_app.config.get("CHUNK_OVERLAP", 50),
        )
        self._embed_model = DeepSeekEmbedding()
        self._llm = DeepSeekLLM()

        # 设置 LlamaIndex 全局默认
        Settings.embed_model = self._embed_model
        Settings.llm = self._llm

        # 缓存已加载的索引: {kb_id: VectorStoreIndex}
        self._indices: dict = {}

    # ── 索引持久化路径 ────────────────────────────────

    def _index_dir(self, kb_id: int) -> str:
        return os.path.join(self._base_dir, f"kb_{kb_id}")

    def _persist_path(self, kb_id: int) -> str:
        return self._index_dir(kb_id)

    # ── 索引获取 / 创建 ─────────────────────────────────

    def get_index(self, kb_id: int) -> VectorStoreIndex:
        """获取知识库的索引（优先缓存 → 磁盘加载 → 新建空索引）。"""
        if kb_id in self._indices:
            return self._indices[kb_id]

        persist_dir = self._persist_path(kb_id)
        if os.path.exists(persist_dir) and os.listdir(persist_dir):
            try:
                storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
                index = load_index_from_storage(storage_context)
                self._indices[kb_id] = index
                return index
            except Exception:
                current_app.logger.warning(
                    "无法加载知识库 %s 的索引，将重建", kb_id, exc_info=True
                )

        # 新建空索引
        index = VectorStoreIndex(
            nodes=[],
            storage_context=StorageContext.from_defaults(
                vector_store=SimpleVectorStore(),
            ),
            embed_model=self._embed_model,
        )
        self._indices[kb_id] = index
        return index

    def _persist(self, kb_id: int) -> None:
        """持久化索引到磁盘。"""
        if kb_id in self._indices:
            persist_dir = self._persist_path(kb_id)
            os.makedirs(persist_dir, exist_ok=True)
            self._indices[kb_id].storage_context.persist(persist_dir=persist_dir)

    # ── 文档操作 ────────────────────────────────────────

    def add_document(
        self,
        file_path: str,
        file_type: str,
        doc_id: int,
        file_name: str,
        kb_id: int,
    ) -> int:
        """上传并索引一个文档。

        Returns:
            生成的节点（chunk）数量
        """
        # 1. 解析为 Document 列表
        ref_doc_id = f"doc_{doc_id}"
        documents = _load_documents(file_path, file_type, ref_doc_id, file_name)

        # 2. 切分为节点
        all_nodes = []
        for doc in documents:
            nodes = self._splitter.get_nodes_from_documents([doc])
            all_nodes.extend(nodes)

        if not all_nodes:
            raise ValueError("文档切分失败")

        # 3. 生成 embedding 并插入索引
        for node in all_nodes:
            node.embedding = self._embed_model._get_text_embedding(node.text)

        index = self.get_index(kb_id)
        index.insert_nodes(all_nodes)

        # 4. 持久化
        self._persist(kb_id)

        return len(all_nodes)

    def delete_document(self, doc_id: int, kb_id: int) -> None:
        """从索引中删除指定文档的所有节点。"""
        ref_doc_id = f"doc_{doc_id}"
        index = self.get_index(kb_id)

        try:
            index.delete_ref_doc(ref_doc_id, delete_from_docstore=True)
        except Exception:
            current_app.logger.warning(
                "删除文档 %s 时出错", ref_doc_id, exc_info=True
            )

        self._persist(kb_id)

    # ── 问答 ─────────────────────────────────────────────

    def query(
        self, question: str, kb_id: int, top_k: int = 4
    ) -> Tuple[str, List[dict]]:
        """RAG 问答。

        Returns:
            (answer, source_docs) — 保持与旧 RAGService.ask() 相同的返回格式
        """
        index = self.get_index(kb_id)

        # 检索
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(question)

        if not nodes:
            return "抱歉，在知识库中未找到与您问题相关的内容，请尝试换个方式提问。", []

        # 格式化上下文
        context_parts = []
        for i, node in enumerate(nodes, 1):
            source = node.metadata.get("file_name", "未知来源")
            context_parts.append(f"[来源{i}: {source}]\n{node.text}")

        context = "\n\n".join(context_parts)
        prompt = SYSTEM_PROMPT.format(context=context)

        # 调用 LLM
        answer = self._llm._call_api(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.3,
        )

        # 提取来源文档
        source_docs = self._extract_source_docs(nodes)

        return answer, source_docs

    def _extract_source_docs(self, nodes) -> List[dict]:
        """从检索节点中提取去重后的来源文档信息。"""
        sources = []
        seen = set()
        for node in nodes:
            file_name = node.metadata.get("file_name", "未知")
            if file_name in seen:
                continue
            seen.add(file_name)
            sources.append({
                "file_name": file_name,
                "content": node.text[:200],
            })
        return sources

    # ── 维护 ─────────────────────────────────────────────

    def delete_index(self, kb_id: int) -> None:
        """删除知识库的所有向量数据。"""
        # 清理缓存
        self._indices.pop(kb_id, None)

        # 清理磁盘
        index_dir = self._index_dir(kb_id)
        if os.path.exists(index_dir):
            shutil.rmtree(index_dir, ignore_errors=True)

    def delete_all_indices(self) -> None:
        """清空所有知识库的向量数据（用于格式化数据库）。"""
        self._indices.clear()
        if os.path.exists(self._base_dir):
            for entry in os.listdir(self._base_dir):
                entry_path = os.path.join(self._base_dir, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path, ignore_errors=True)
                else:
                    try:
                        os.remove(entry_path)
                    except FileNotFoundError:
                        continue
