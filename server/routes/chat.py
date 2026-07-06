"""
问答对话路由
提供RAG问答和对话历史查询接口
"""
import uuid
import json
from flask import Blueprint, request, current_app
from models import db
from models.chat_history import ChatHistory
from models.knowledge_base import KnowledgeBase
from utils.response import success, error, page_response

# 创建问答蓝图
chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/ask', methods=['POST'])
def ask():
    """
    RAG知识库问答接口
    请求参数: question(问题), kb_id(知识库ID), session_id(会话ID，可选)
    返回: AI回答和参考来源
    """
    data = request.get_json()
    if not data:
        return error('请提供问题信息')

    question = data.get('question', '').strip()
    kb_id = data.get('kb_id')
    session_id = data.get('session_id', str(uuid.uuid4().hex[:16]))

    if not question:
        return error('问题不能为空')
    if not kb_id:
        return error('请选择知识库')

    # 验证知识库是否存在
    kb = KnowledgeBase.query.get(kb_id)
    if not kb or kb.status != 1:
        return error('知识库不存在或已禁用')

    # 调用 RAG 服务进行问答
    try:
        from services.llama.index_manager import IndexManager
        index_manager = IndexManager()
        answer, source_docs = index_manager.query(
            question=question,
            kb_id=kb_id,
            top_k=current_app.config.get('RETRIEVER_TOP_K', 4),
        )
    except Exception as e:
        return error(f'问答服务异常: {str(e)}')

    # 保存对话记录
    chat = ChatHistory(
        user_id=current_app.config['SYSTEM_USER_ID'],
        kb_id=kb_id,
        session_id=session_id,
        question=question,
        answer=answer,
        source_docs=json.dumps(source_docs, ensure_ascii=False)
    )
    db.session.add(chat)
    db.session.commit()

    return success({
        'answer': answer,
        'source_docs': source_docs,
        'session_id': session_id,
        'chat_id': chat.id
    })


@chat_bp.route('/history', methods=['GET'])
def get_history():
    """
    获取对话历史列表（分页）
    查询参数: page, page_size, kb_id(可选)
    普通用户只能查看自己的记录，管理员可查看所有
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    kb_id = request.args.get('kb_id', type=int)

    query = ChatHistory.query

    # 普通用户只能查看自己的对话记录

    if kb_id:
        query = query.filter_by(kb_id=kb_id)

    query = query.order_by(ChatHistory.create_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [item.to_dict() for item in pagination.items]
    return page_response(items, pagination.total, page, page_size)


@chat_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """
    获取指定会话的所有对话记录
    路径参数: session_id(会话ID)
    """
    query = ChatHistory.query.filter_by(session_id=session_id)

    # 普通用户只能查看自己的对话

    chats = query.order_by(ChatHistory.create_time.asc()).all()
    return success([chat.to_dict() for chat in chats])
