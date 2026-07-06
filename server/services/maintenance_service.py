import os
import shutil

from flask import current_app
from sqlalchemy import text

from models import db
from models.chat_history import ChatHistory
from models.document import Document
from models.knowledge_base import KnowledgeBase
from services.llama.index_manager import IndexManager


class MaintenanceService:
    """Dangerous maintenance operations exposed from the settings page."""

    TABLES_TO_RESET = (
        ChatHistory.__tablename__,
        Document.__tablename__,
        KnowledgeBase.__tablename__,
    )

    def format_database(self):
        upload_folder = os.path.abspath(current_app.config['UPLOAD_FOLDER'])

        try:
            db.session.query(ChatHistory).delete(synchronize_session=False)
            db.session.query(Document).delete(synchronize_session=False)
            db.session.query(KnowledgeBase).delete(synchronize_session=False)

            for table_name in self.TABLES_TO_RESET:
                db.session.execute(text(f'ALTER TABLE {table_name} AUTO_INCREMENT = 1'))

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        self._clear_directory(upload_folder)

        # 使用 IndexManager 清理所有向量索引
        index_manager = IndexManager()
        index_manager.delete_all_indices()

        return {
            'knowledge_base_count': 0,
            'document_count': 0,
            'chat_history_count': 0,
        }

    def _clear_directory(self, directory_path):
        if not os.path.isdir(directory_path):
            os.makedirs(directory_path, exist_ok=True)
            return

        for entry_name in os.listdir(directory_path):
            entry_path = os.path.join(directory_path, entry_name)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path, ignore_errors=True)
            else:
                try:
                    os.remove(entry_path)
                except FileNotFoundError:
                    continue
