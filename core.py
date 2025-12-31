import sqlite3
import subprocess
import os
from datetime import datetime, timedelta

# Caminho do banco na VPS
DB_PATH = '/opt/vpspack/data.db'
IS_WINDOWS = os.name == 'nt'

def get_db():
    if not os.path.exists(os.path.dirname(DB_PATH)) and not IS_WINDOWS:
        os.makedirs(os.path.dirname(DB_PATH))
    db_file = 'data.db' if IS_WINDOWS else DB_PATH
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    cols = [r["name"] for r in rows]
    return column in cols

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Tabela base
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        uuid TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,  -- Login SSH (Sistema Linux)
        password TEXT NOT NULL,
        name TEXT,                      -- Nome do Cliente
        cpf TEXT UNIQUE,                -- Login do Painel WEB (opcional)
        email TEXT,
        hwid TEXT,
        limit_conn INTEGER DEFAULT 1,
        expiration_date DATE,
        is_active BOOLEAN DEFAULT 1
    )''')
    conn.commit()

    # Migracao: adiciona colunas novas se nao existirem
    if not _column_exists(conn, "users", "api_token"):
        c.execute("ALTER TABLE users ADD COLUMN api_token TEXT")
        conn.commit()

    if not _column_exists(conn, "users", "token_created_at"):
        c.execute("ALTER TABLE users ADD COLUMN token_created_at TEXT")
        conn.commit()

    conn.close()

# --- FUNCOES DO SISTEMA (LINUX) ---

def sys_count_online(username):
    if IS_WINDOWS:
        return 0
    try:
        cmd = f"pgrep -c -u {username} sshd"
        result = subprocess.check_output(cmd, shell=True)
        return int(result.strip())
    except:
        return 0

def sys_kill_user(username):
    if IS_WINDOWS:
        return True
    try:
        subprocess.run(['pkill', '-u', username], stderr=subprocess.DEVNULL)
        return True
    except:
        return False

def sys_create_user(username, password):
    if IS_WINDOWS:
        return True
    try:
        subprocess.run(['useradd', '-M', '-s', '/bin/false', username], check=True)
        p = subprocess.Popen(['chpasswd'], stdin=subprocess.PIPE)
        p.communicate(input=f"{username}:{password}".encode())
        return True
    except:
        return False

def sys_delete_user(username):
    if IS_WINDOWS:
        return True
    try:
        sys_kill_user(username)
        subprocess.run(['userdel', '-r', username], check=True)
        return True
    except:
        return False

def sys_toggle_user(username, active):
    if IS_WINDOWS:
        return True
    try:
        if active:
            subprocess.run(['passwd', '-u', username])
        else:
            subprocess.run(['passwd', '-l', username])
            sys_kill_user(username)
        return True
    except:
        return False
