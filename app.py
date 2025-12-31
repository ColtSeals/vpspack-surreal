from flask import Flask, render_template, request, redirect, session, jsonify
from functools import wraps
from core import *
import uuid

app = Flask(__name__)
app.secret_key = 'CHAVE_ULTRA_SECRETA_MUDE_ISSO_AGORA'

init_db()

# -----------------------------
# Helpers
# -----------------------------
def only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def is_expired(expiration_date: str) -> bool:
    # expiration_date: 'YYYY-MM-DD'
    if not expiration_date:
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    return expiration_date < today

def user_to_dict(u):
    return {
        "uuid": u["uuid"],
        "username": u["username"],
        "name": u["name"] or "",
        "cpf": u["cpf"] or "",
        "email": u["email"] or "",
        "hwid": u["hwid"] or "",
        "limit_conn": int(u["limit_conn"] or 1),
        "expiration_date": u["expiration_date"] or "",
        "is_active": bool(u["is_active"]),
        "online": sys_count_online(u["username"]),
    }

# -----------------------------
# Decorators
# -----------------------------
def login_required(f):
    # usado APENAS para painel web (admin)
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def api_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"status": "error", "message": "Token ausente"}), 401

        token = auth.replace("Bearer ", "").strip()
        if not token:
            return jsonify({"status": "error", "message": "Token invalido"}), 401

        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE api_token = ?", (token,)).fetchone()
        conn.close()

        if not u:
            return jsonify({"status": "error", "message": "Token invalido"}), 401

        # regras de bloqueio/validade (reforco)
        if not u["is_active"]:
            return jsonify({"status": "error", "message": "Conta bloqueada/pendente"}), 403
        if is_expired(u["expiration_date"] or ""):
            return jsonify({"status": "error", "message": "Conta expirada"}), 403

        request.user_row = u
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# API: CREATE (semi-aberta)
# -----------------------------
@app.route('/api/create', methods=['POST'])
def api_create():
    data = request.json or {}

    username = (data.get('username') or "").strip()
    password = (data.get('password') or "")
    cpf = only_digits(data.get('cpf') or "")

    name = (data.get('name') or "").strip()
    email = (data.get('email') or "").strip()
    hwid = (data.get('hwid') or "").strip()

    if not username or not password or not cpf:
        return jsonify({'status': 'error', 'message': 'Campos SSH User, Senha e CPF sao obrigatorios'}), 400

    # Permissao: se admin web estiver logado, cria ativo com parametros
    if session.get('logged_in'):
        status_ativo = 1
        dias_validade = int(data.get('days', 30))
        limite_conn = int(data.get('limit', 1))
    else:
        status_ativo = 0
        dias_validade = 0
        limite_conn = 1

    if sys_create_user(username, password):
        if status_ativo == 0:
            sys_toggle_user(username, False)

        expiry = (datetime.now() + timedelta(days=dias_validade)).strftime('%Y-%m-%d')

        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (str(uuid.uuid4()), username, password, name, cpf, email, hwid, limite_conn, expiry, status_ativo))
            conn.commit()

            msg = 'Usuario criado com sucesso!' if status_ativo else 'Cadastro realizado! Aguarde aprovacao.'
            return jsonify({'status': 'success', 'message': msg})

        except Exception as e:
            # rollback do Linux user se duplicar no DB
            try:
                sys_delete_user(username)
            except:
                pass
            return jsonify({'status': 'error', 'message': 'Usuario ou CPF ja existe'}), 409
        finally:
            conn.close()

    return jsonify({'status': 'error', 'message': 'Erro ao criar no sistema Linux'}), 500

# -----------------------------
# API: LOGIN (APP)
# - aceita username OU cpf no campo "login"
# -----------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}

    login_value = (data.get("login") or "").strip()  # pode ser username ou cpf
    password = (data.get("password") or "")
    hwid = (data.get("hwid") or "").strip()

    if not login_value or not password:
        return jsonify({"status": "error", "message": "Login e senha sao obrigatorios"}), 400

    conn = get_db()

    # Se for CPF (11 digitos), loga por cpf; senao por username
    digits = only_digits(login_value)
    if len(digits) == 11:
        u = conn.execute("SELECT * FROM users WHERE cpf = ? AND password = ?", (digits, password)).fetchone()
    else:
        u = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (login_value, password)).fetchone()

    if not u:
        conn.close()
        return jsonify({"status": "error", "message": "Credenciais invalidas"}), 401

    if not u["is_active"]:
        conn.close()
        return jsonify({"status": "error", "message": "Conta bloqueada/pendente"}), 403

    if is_expired(u["expiration_date"] or ""):
        conn.close()
        return jsonify({"status": "error", "message": "Conta expirada"}), 403

    # Regra HWID:
    # - se ja tem hwid salvo e o app enviar outro -> bloqueia
    if (u["hwid"] or "") and hwid and (u["hwid"] != hwid):
        conn.close()
        return jsonify({"status": "error", "message": "HWID nao autorizado"}), 403

    # - se nao tem hwid salvo e app enviar, salva 1a vez
    if not (u["hwid"] or "") and hwid:
        conn.execute("UPDATE users SET hwid = ? WHERE uuid = ?", (hwid, u["uuid"]))
        conn.commit()

    token = str(uuid.uuid4())
    conn.execute(
        "UPDATE users SET api_token = ?, token_created_at = ? WHERE uuid = ?",
        (token, datetime.now().isoformat(), u["uuid"])
    )
    conn.commit()

    u2 = conn.execute("SELECT * FROM users WHERE uuid = ?", (u["uuid"],)).fetchone()
    conn.close()

    return jsonify({
        "status": "success",
        "token": token,
        "user": user_to_dict(u2)
    })

# -----------------------------
# API: PROFILE (APP)
# -----------------------------
@app.route('/api/profile', methods=['GET'])
@api_token_required
def api_profile():
    u = request.user_row
    return jsonify({
        "status": "success",
        "user": user_to_dict(u)
    })

# -----------------------------
# API: LOGOUT (APP) - opcional
# -----------------------------
@app.route('/api/logout', methods=['POST'])
@api_token_required
def api_logout():
    u = request.user_row
    conn = get_db()
    conn.execute("UPDATE users SET api_token = NULL, token_created_at = NULL WHERE uuid = ?", (u["uuid"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Logout ok"})

# -----------------------------
# API: ONLINE (ADMIN WEB)
# -----------------------------
@app.route('/api/online', methods=['GET'])
@login_required
def api_online():
    conn = get_db()
    users = conn.execute('SELECT username, limit_conn FROM users').fetchall()
    conn.close()

    data = []
    for u in users:
        qtd = sys_count_online(u['username'])
        data.append({'user': u['username'], 'online': qtd, 'limit': u['limit_conn']})
    return jsonify(data)

# -----------------------------
# WEB LOGIN (ADMIN)
# -----------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form['username']
        password = request.form['password']

        # admin fixo (troque isso depois!)
        if login_input == 'admin' and password == 'admin':
            session['logged_in'] = True
            return redirect('/')

        # cliente ainda nao tem painel web (mantive seu comportamento)
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE cpf = ? AND password = ?', (only_digits(login_input), password)).fetchone()
        conn.close()

        if user:
            if not user['is_active']:
                return render_template('login.html', error="Sua conta esta bloqueada/pendente.")
            return render_template('login.html', error="Painel do Cliente em Breve")

        return render_template('login.html', error="Dados invalidos")

    return render_template('login.html')

# -----------------------------
# WEB ADMIN HOME
# -----------------------------
@app.route('/')
@login_required
def index():
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/action/kick/<username>')
@login_required
def action_kick(username):
    sys_kill_user(username)
    return redirect('/')

@app.route('/action/toggle/<uuid>')
@login_required
def action_toggle(uuid):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid,)).fetchone()

    new_status = 0 if u['is_active'] else 1
    sys_toggle_user(u['username'], bool(new_status))

    conn.execute('UPDATE users SET is_active=? WHERE uuid=?', (new_status, uuid))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/action/delete/<uuid>')
@login_required
def action_delete(uuid):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid,)).fetchone()
    if u:
        sys_delete_user(u['username'])
        conn.execute('DELETE FROM users WHERE uuid=?', (uuid,))
        conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
