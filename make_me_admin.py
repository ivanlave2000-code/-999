import sqlite3
from database import DB_NAME

# Укажи логин своего аккаунта на сайте
my_username = "khan"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Обновляем значение is_admin на 1
cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (my_username,))
conn.commit()

if cursor.rowcount > 0:
    print(f"✅ Пользователь '{my_username}' теперь администратор!")
else:
    print(f"❌ Пользователь с логином '{my_username}' не найден.")

conn.close()