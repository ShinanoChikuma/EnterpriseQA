import os


class AppConfig:
    """Application configuration."""

    MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3308))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '123456')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'db_enterprise_qa')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.environ.get('SECRET_KEY', 'enterprise-qa-secret-key-2024')
    JWT_EXPIRATION = int(os.environ.get('JWT_EXPIRATION', 86400))

    SYSTEM_USER_ID = int(os.environ.get('SYSTEM_USER_ID', 1))

    DEEPSEEK_API_KEY = os.environ.get(
        'DEEPSEEK_API_KEY',
        ''
    )
    DEEPSEEK_CHAT_MODEL = os.environ.get('DEEPSEEK_CHAT_MODEL', 'deepseek-chat')
    DEEPSEEK_EMBED_MODEL = os.environ.get('DEEPSEEK_EMBED_MODEL', 'deepseek-embedding')

    VECTOR_STORE_DIR = os.environ.get(
        'VECTOR_STORE_DIR',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vector_data')
    )
    API_SETTINGS_FILE = os.environ.get(
        'API_SETTINGS_FILE',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_settings.json')
    )

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        'txt', 'md', 'pdf', 'docx', 'doc', 'epub', 'html', 'htm', 'csv', 'rtf', 'xlsx'
    }

    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

    EMBED_BATCH_SIZE = 10
    EMBED_MAX_RETRIES = 3
    RETRIEVER_TOP_K = 4
