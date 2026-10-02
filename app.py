import os
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
import database

app = Flask(__name__)

# Секретный ключ для работы сессий Flask
app.secret_key = os.urandom(24)

# Инициализируем БД при старте приложения
database.init_db()


def get_current_user():
    """Вспомогательная функция для получения текущего пользователя из сессии"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return database.get_user_by_id(user_id)


def get_or_create_user_code(user_id):
    """Генерация или получение существующего кода для привязки"""
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT code FROM auth_codes WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        code = row[0]
    else:
        code = str(random.randint(100000, 999999))
        cursor.execute(
            "INSERT OR REPLACE INTO auth_codes (code, telegram_id) VALUES (?, ?)",
            (code, user_id)
        )
        conn.commit()
        
    conn.close()
    return code


@app.route("/")
def index():
    user = get_current_user()
    error = session.pop("error", None)
    link_message = session.pop("link_message", None)

    return render_template(
        "index.html", user=user, error=error, link_message=link_message
    )


@app.route("/admin")
def admin_page():
    user = get_current_user()
    
    # Защита: доступ только для авторизованных админов
    if not user or not user.get("is_admin"):
        session["error"] = "Доступ запрещен!"
        return redirect(url_for("index"))

    repairs = database.get_all_repairs()
    return render_template("admin.html", user=user, repairs=repairs)


@app.route('/admin/update_status/<int:repair_id>', methods=['POST'])
def update_status(repair_id):
    user = get_current_user()
    
    # Проверка: залогинен ли юзер и есть ли у него права админа
    if not user or not user.get('is_admin'):
        flash('У вас нет прав для изменения статуса!', 'danger')
        return redirect(url_for('index'))

    new_status = request.form.get('status')
    if new_status:
        database.update_repair_status(repair_id, new_status)
        flash(f'Статус заказа #{repair_id} изменен на «{new_status}»', 'success')

    return redirect(url_for('admin_page'))


@app.route("/admin/create-repair", methods=["GET", "POST"])
def admin_create_repair():
    user = get_current_user()

    # Защита: доступ только для админов
    if not user or not user.get("is_admin"):
        flash("У вас нет прав для доступа!", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        # Админ может выбрать клиента по его ID или username
        user_id = request.form.get("user_id")
        device_name = request.form.get("device_name", "").strip()
        description = request.form.get("description", "").strip()

        if not user_id or not device_name:
            users = database.get_all_users()  # Список пользователей для выпадающего списка
            flash("Выберите пользователя и укажите название устройства!", "danger")
            return render_template("admin_create_repair.html", user=user, users=users)

        database.add_repair(user_id, device_name, description)
        flash("✅ Новая заявка на ремонт успешно создана!", "success")
        return redirect(url_for("admin_page"))

    # На GET запрос получаем список всех пользователей, чтобы админ мог выбрать клиента
    users = database.get_all_users()
    return render_template("admin_create_repair.html", user=user, users=users)


@app.route("/my-repairs")
def my_repairs():
    user = get_current_user()
    if not user:
        session["error"] = "Спочатку увійдіть в акаунт!"
        return redirect(url_for("login"))

    user_repairs = database.get_user_repairs(user["id"])
    return render_template("my_repairs.html", user=user, repairs=user_repairs)


@app.route("/link_telegram", methods=["GET", "POST"])
def link_telegram_page():
    user = get_current_user()
    
    if not user:
        session["error"] = "Спочатку увійдіть в акаунт!"
        return redirect(url_for("login"))

    if user.get("telegram_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        
        if not code or len(code) != 6:
            return render_template("link_telegram.html", user=user, error="Код має складатися з 6 цифр!")

        success, message = database.link_telegram_by_code(user["id"], code)
        
        if success:
            session["link_message"] = "✅ Telegram успішно прив'язано!"
            return redirect(url_for("index"))
        else:
            return render_template("link_telegram.html", user=user, error=message)

    bot_username = "servise_pro_bot"
    tg_link = f"https://t.me/{bot_username}"

    return render_template("link_telegram.html", user=user, tg_link=tg_link)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Проверяем пользователя через функцию модуля database
        user = database.check_user(username, password)
        
        if user:
            session['user_id'] = user['id']
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'danger')

    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        user = get_current_user()
        return render_template("register.html", user=user)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("register.html", error="Заповніть всі поля!")

        if len(password) < 6:
            return render_template("register.html", error="Пароль має бути не менше 6 символів!")

        success, message = database.register_user(username, password)
        if success:
            user = database.check_user(username, password)
            if user:
                session["user_id"] = user["id"]
            return redirect(url_for("index"))
        else:
            return render_template("register.html", error=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)