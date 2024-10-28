import psycopg2
from psycopg2.extras import DictCursor
from config import DB_CONFIG

def get_db_connection():
    try:
        conn = psycopg2.connect(
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        return conn
    except Exception as e:
        raise Exception(f"Database connection error: {str(e)}")

def execute_query(query, params=None):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query, params)
            conn.commit()
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()
