import argparse
import os

from app import create_app
from models import db
from models.document import Document
from models.knowledge_base import KnowledgeBase
from services.llama.index_manager import IndexManager


def main():
    parser = argparse.ArgumentParser(description='Rebuild local vector store.')
    parser.add_argument('--doc-id', type=int, action='append', help='Only reindex specific document IDs.')
    parser.add_argument('--kb-id', type=int, action='append', help='Only reindex documents in specific knowledge base IDs.')
    parser.add_argument('--clear-store', action='store_true', help='Clear the local vector store before reindexing.')
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        index_manager = IndexManager()

        if args.clear_store:
            index_manager.delete_all_indices()

        query = Document.query
        if args.doc_id:
            query = query.filter(Document.id.in_(args.doc_id))
        if args.kb_id:
            query = query.filter(Document.kb_id.in_(args.kb_id))

        documents = query.order_by(Document.id.asc()).all()
        if not documents:
            print('No documents matched.')
            return

        touched_kb_ids = set()

        for doc in documents:
            if not os.path.exists(doc.file_path):
                print(f'Skip missing file for doc {doc.id}: {doc.file_path}')
                continue

            print(f'Reindex doc {doc.id}: {doc.file_name}')
            index_manager.delete_document(doc.id, doc.kb_id)
            chunk_count = index_manager.add_document(
                file_path=doc.file_path,
                file_type=doc.file_type,
                doc_id=doc.id,
                file_name=doc.file_name,
                kb_id=doc.kb_id,
            )
            doc.status = 'vectorized'
            doc.chunk_count = chunk_count
            touched_kb_ids.add(doc.kb_id)

        for kb_id in touched_kb_ids:
            kb = db.session.get(KnowledgeBase, kb_id)
            if kb:
                kb.doc_count = Document.query.filter_by(kb_id=kb_id, status='vectorized').count()

        db.session.commit()
        print('Reindex complete.')


if __name__ == '__main__':
    main()
