import os
import uuid

from flask import Blueprint, current_app, request

from models import db
from models.document import Document
from models.knowledge_base import KnowledgeBase
from utils.response import error, page_response, success


doc_bp = Blueprint('document', __name__)


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    )


@doc_bp.route('/list', methods=['GET'])
def get_list():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    kb_id = request.args.get('kb_id', type=int)

    query = Document.query
    if kb_id:
        query = query.filter_by(kb_id=kb_id)

    query = query.order_by(Document.create_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [item.to_dict() for item in pagination.items]
    return page_response(items, pagination.total, page, page_size)


@doc_bp.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return error('请选择要上传的文件')

    file = request.files['file']
    kb_id = request.form.get('kb_id', type=int)

    if not kb_id:
        return error('请选择知识库')

    if file.filename == '':
        return error('请选择要上传的文件')

    if not allowed_file(file.filename):
        return error(
            f"不支持的文件类型，仅支持: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}"
        )

    kb = KnowledgeBase.query.get(kb_id)
    if not kb:
        return error('知识库不存在')

    file_ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{file_ext}'
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    file.save(file_path)

    file_size = os.path.getsize(file_path)

    doc = Document(
        kb_id=kb_id,
        file_name=file.filename,
        file_path=file_path,
        file_size=file_size,
        file_type=file_ext,
        creator_id=current_app.config['SYSTEM_USER_ID'],
    )
    db.session.add(doc)
    db.session.commit()

    try:
        from services.llama.index_manager import IndexManager
    except Exception as exc:
        doc.status = 'failed'
        db.session.commit()
        return error(f'索引服务初始化失败: {exc}')

    try:
        index_manager = IndexManager()
        chunk_count = index_manager.add_document(
            file_path=file_path,
            file_type=file_ext,
            doc_id=doc.id,
            file_name=file.filename,
            kb_id=kb_id,
        )

        doc.status = 'vectorized'
        doc.chunk_count = chunk_count
        kb.doc_count = Document.query.filter_by(kb_id=kb_id, status='vectorized').count()
        db.session.commit()
    except Exception as exc:
        doc.status = 'failed'
        db.session.commit()
        err_msg = str(exc)
        return error(f'文档向量化失败: {err_msg}')

    return success(doc.to_dict(), '上传成功')


@doc_bp.route('/<int:doc_id>', methods=['DELETE'])
def delete(doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return error('文档不存在', 404)

    kb_id = doc.kb_id

    try:
        from services.llama.index_manager import IndexManager

        index_manager = IndexManager()
        index_manager.delete_document(doc.id, kb_id)
    except Exception:
        pass

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.session.delete(doc)

    kb = KnowledgeBase.query.get(kb_id)
    if kb:
        kb.doc_count = Document.query.filter_by(kb_id=kb_id, status='vectorized').count() - 1
        if kb.doc_count < 0:
            kb.doc_count = 0

    db.session.commit()
    return success(message='删除成功')
