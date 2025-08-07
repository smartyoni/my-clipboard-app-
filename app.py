from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)

DB_FILE = "memo_app.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        display_order INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS memos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        display_order INTEGER,
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
    )
    ''')
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO categories (name, display_order) VALUES (?, ?)", ('일반', 0))
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# 메인 페이지 라우트: 이제 HTML 파일을 직접 렌더링합니다.
@app.route('/')
def index():
    return render_template('index.html')

# --- 이하 API 라우트들은 이전과 동일합니다 ---
@app.route('/api/categories', methods=['GET', 'POST'])
def handle_categories():
    conn = get_db_connection()
    if request.method == 'GET':
        categories = conn.execute('SELECT * FROM categories ORDER BY display_order, id').fetchall()
        conn.close()
        return jsonify({'categories': [dict(row) for row in categories]})
    if request.method == 'POST':
        data = request.json; name = data.get('name')
        if not name: return jsonify({'error': '카테고리 이름이 필요합니다.'}), 400
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(display_order) FROM categories"); max_order = cursor.fetchone()[0]; new_order = (max_order or 0) + 1
        try:
            cursor.execute("INSERT INTO categories (name, display_order) VALUES (?, ?)", (name, new_order)); conn.commit()
        except sqlite3.IntegrityError: return jsonify({'error': '이미 존재하는 카테고리 이름입니다.'}), 409
        finally: conn.close()
        return jsonify({'status': 'success'}), 201

@app.route('/api/categories/<int:category_id>', methods=['PUT', 'DELETE'])
def handle_category(category_id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.json; name = data.get('name')
        if not name: return jsonify({'error': '새 카테고리 이름이 필요합니다.'}), 400
        try:
            conn.execute('UPDATE categories SET name = ? WHERE id = ?', (name, category_id)); conn.commit()
        except sqlite3.IntegrityError: return jsonify({'error': '이미 존재하는 카테고리 이름입니다.'}), 409
        finally: conn.close()
        return jsonify({'status': 'success'})
    if request.method == 'DELETE':
        cursor = conn.cursor(); cursor.execute("SELECT id FROM categories WHERE name = '일반'"); default_category_row = cursor.fetchone()
        if default_category_row is None or default_category_row['id'] == category_id: return jsonify({'error': '기본 카테고리는 삭제할 수 없습니다.'}), 400
        default_category_id = default_category_row['id']
        conn.execute('UPDATE memos SET category_id = ? WHERE category_id = ?', (default_category_id, category_id))
        conn.execute('DELETE FROM categories WHERE id = ?', (category_id,)); conn.commit(); conn.close()
        return jsonify({'status': 'success'})

@app.route('/api/memos', methods=['GET', 'POST'])
def handle_memos():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.json; now = datetime.now().isoformat(); cursor = conn.cursor()
        cursor.execute("SELECT MAX(display_order) FROM memos WHERE category_id = ?", (data['category_id'],))
        max_order = cursor.fetchone()[0]; new_order = (max_order or 0) + 1
        cursor.execute('INSERT INTO memos (title, content, created_at, updated_at, display_order, category_id) VALUES (?, ?, ?, ?, ?, ?)',(data['title'], data['content'], now, now, new_order, data['category_id'])); conn.commit(); conn.close()
        return jsonify({'status': 'success'}), 201
    if request.method == 'GET':
        category_id = request.args.get('category_id', type=int)
        if not category_id: return jsonify({'memos': []})
        memos = conn.execute('SELECT * FROM memos WHERE category_id = ? ORDER BY display_order', (category_id,)).fetchall(); conn.close()
        return jsonify({'memos': [dict(row) for row in memos]})

@app.route('/api/memos/<int:memo_id>', methods=['PUT', 'DELETE'])
def handle_memo(memo_id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.json; now = datetime.now().isoformat()
        conn.execute('UPDATE memos SET title = ?, content = ?, category_id = ?, updated_at = ? WHERE id = ?',(data['title'], data['content'], data['category_id'], now, memo_id)); conn.commit(); conn.close()
        return jsonify({'status': 'success'})
    if request.method == 'DELETE':
        conn.execute('DELETE FROM memos WHERE id = ?', (memo_id,)); conn.commit(); conn.close()
        return jsonify({'status': 'success'})

@app.route('/api/memos/reorder', methods=['POST'])
def reorder_memos():
    data = request.json; ordered_ids = data['ordered_ids']; conn = get_db_connection(); cursor = conn.cursor()
    for index, memo_id in enumerate(ordered_ids):
        cursor.execute('UPDATE memos SET display_order = ? WHERE id = ?', (index, memo_id))
    conn.commit(); conn.close()
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
