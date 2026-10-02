import sqlite3
import random
import werkzeug.security

DB_NAME = "users.db"  


def get_all_users():
    """Получить список всех пользователей для выбора при создании заказа"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users ORDER BY username ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def init_db():
    """Инициализация базы данных и автоматическое создание таблиц"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Таблиця користувачів
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            telegram_id INTEGER UNIQUE,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Таблиця часових кодів авторизації Telegram
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_codes (
            code TEXT PRIMARY KEY,
            telegram_id INTEGER NOT NULL,
            first_name TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3.Таблиця ремонтів
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'В работе',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Динамічна перевірка та доповнення відсутніх колонок
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    if "password_hash" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "telegram_id" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN telegram_id INTEGER UNIQUE")
    if "is_admin" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def register_user(username, password):
    """Регистрация нового пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    hashed_password = werkzeug.security.generate_password_hash(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hashed_password),
        )
        conn.commit()
        conn.close()
        return True, "Успешная регистрация!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Пользователь с таким логином уже существует!"


def check_user(username, password):
    """Проверка логина и пароля при входе"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, password_hash, telegram_id, is_admin FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    conn.close()

    if row and werkzeug.security.check_password_hash(row[2], password):
        return {"id": row[0], "username": row[1], "telegram_id": row[3], "is_admin": row[4]}
    return None


def get_user_by_username(username):
    """Получение пользователя по логину"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, telegram_id, is_admin FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, telegram_id, is_admin FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def generate_auth_code(telegram_id, first_name="", username=""):
    """Генерация 6-значного кода для привязки Telegram к сайту"""
    code = str(random.randint(100000, 999999))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM auth_codes WHERE telegram_id = ?", (telegram_id,))
    cursor.execute(
        "INSERT INTO auth_codes (code, telegram_id, first_name, username) VALUES (?, ?, ?, ?)",
        (code, telegram_id, first_name, username)
    )

    conn.commit()
    conn.close()
    return code


def link_telegram_by_code(user_id, code):
    """Привязка Telegram к аккаунту сайта по коду"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT telegram_id FROM auth_codes WHERE code = ?", (code,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Неверный или устаревший код!"

        telegram_id = row[0]

        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        if cursor.fetchone():
            conn.close()
            return False, "Этот Telegram-аккаунт уже привязан к другому профилю!"

        cursor.execute("UPDATE users SET telegram_id = ? WHERE id = ?", (telegram_id, user_id))
        cursor.execute("DELETE FROM auth_codes WHERE code = ?", (code,))

        conn.commit()
        conn.close()
        return True, "Telegram успешно привязан!"

    except Exception as e:
        conn.close()
        return False, f"Ошибка базы данных: {str(e)}"


def add_repair(user_id, device_name, description):
    """Создание новой заявки на ремонт"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO repairs (user_id, device_name, description, status)
        VALUES (?, ?, ?, 'В работе')
    """, (user_id, device_name, description))
    conn.commit()
    conn.close()


def get_all_repairs():
    """Получить список всех ремонтов с именами клиентов (для админа)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.id, u.username, r.device_name, r.description, r.status, r.created_at
        FROM repairs r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "username": row[1],
            "device_name": row[2],
            "description": row[3],
            "status": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def get_user_repairs(user_id):
    """Получить список ремонтов конкретного пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, device_name, description, status, created_at 
        FROM repairs WHERE user_id = ? ORDER BY id DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "device_name": r[1],
            "description": r[2],
            "status": r[3],
            "created_at": r[4],
        }
        for r in rows
    ]


def update_repair_status(repair_id, new_status):
    """Обновить статус ремонта"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE repairs SET status = ? WHERE id = ?", (new_status, repair_id))
    conn.commit()
    conn.close()
