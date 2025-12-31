from flask import Flask, render_template, request, redirect, session, jsonify
from functools import wraps
from datetime import datetime, timedelta
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
def login_required_page(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({
                "status": "error",
                "message": "Nao autorizado",
                "redirect": "/login"
            }), 401
        return f(*args, **kwargs)
    return decorated

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
        
        if not u["is_active"]:
            return jsonify({"status": "error", "message": "Conta bloqueada/pendente"}), 403
        if is_expired(u["expiration_date"] or ""):
            return jsonify({"status": "error", "message": "Conta expirada"}), 403

        request.user_row = u
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# API: UPDATE USER (ADMIN) - NOVO
# -----------------------------
@app.route('/api/update', methods=['POST'])
@login_required_api
def api_update():
    data = request.json or {}
    
    uuid_user = data.get('uuid')
    username = data.get('username') # apenas para seguranca/check
    
    if not uuid_user:
        return jsonify({'status': 'error', 'message': 'UUID necessario'}), 400

    # Busca user atual
    conn = get_db()
    curr = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid_user,)).fetchone()
    if not curr:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Usuario nao encontrado'}), 404

    # Dados novos
    new_pass = (data.get('password') or "").strip()
    new_name = (data.get('name') or "").strip()
    new_email = (data.get('email') or "").strip()
    new_hwid = (data.get('hwid') or "").strip()
    new_limit = data.get('limit')
    add_days = data.get('days') # se vier numero, soma a hoje

    # Prepara valores finais (se vazio mantem atual)
    final_name = new_name if new_name else curr['name']
    final_email = new_email if new_email else curr['email']
    final_hwid = new_hwid if new_hwid else curr['hwid']
    
    final_limit = curr['limit_conn']
    if new_limit:
        try: final_limit = int(new_limit)
        except: pass
    
    final_exp = curr['expiration_date']
    if add_days:
        try:
            d = int(add_days)
            if d > 0:
                final_exp = (datetime.now() + timedelta(days=d)).strftime('%Y-%m-%d')
        except: pass

    # Se trocou a senha, aplica no sistema
    final_pass = curr['password']
    if new_pass:
        final_pass = new_pass
        sys_change_password(curr['username'], new_pass)

    # Atualiza DB
    conn.execute('''
        UPDATE users SET 
        password=?, name=?, email=?, hwid=?, limit_conn=?, expiration_date=?
        WHERE uuid=?
    ''', (final_pass, final_name, final_email, final_hwid, final_limit, final_exp, uuid_user))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Dados atualizados!'})


# -----------------------------
# API: REGISTER/CREATE
# -----------------------------
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json or {}
    username = (data.get('username') or "").strip()
    password = (data.get('password') or "")
    cpf = only_digits(data.get('cpf') or "")
    name = (data.get('name') or "").strip()
    email = (data.get('email') or "").strip()
    hwid = (data.get('hwid') or "").strip()

    if not username or not password or not cpf:
        return jsonify({'status': 'error', 'message': 'Campos SSH User, Senha e CPF sao obrigatorios'}), 400

    if sys_create_user(username, password):
        sys_toggle_user(username, False) # cria bloqueado
        expiry = datetime.now().strftime('%Y-%m-%d') # vencido hoje
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (str(uuid.uuid4()), username, password, name, cpf, email, hwid, 1, expiry, 0))
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Cadastro realizado! Aguarde aprovacao.'})
        except:
            return jsonify({'status': 'error', 'message': 'Usuario ou CPF ja existe'}), 409
        finally:
            conn.close()
    return jsonify({'status': 'error', 'message': 'Erro sistema Linux'}), 500

@app.route('/api/create', methods=['POST'])
@login_required_api
def api_create():
    data = request.json or {}
    username = (data.get('username') or "").strip()
    password = (data.get('password') or "")
    cpf = only_digits(data.get('cpf') or "")
    name = (data.get('name') or "").strip()
    email = (data.get('email') or "").strip()
    hwid = (data.get('hwid') or "").strip()
    
    if not username or not password or not cpf:
        return jsonify({'status': 'error', 'message': 'Obrigatorio: User, Senha, CPF'}), 400

    days = int(data.get('days', 30))
    limit = int(data.get('limit', 1))

    if sys_create_user(username, password):
        expiry = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (str(uuid.uuid4()), username, password, name, cpf, email, hwid, limit, expiry, 1))
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Criado com sucesso!'})
        except:
            return jsonify({'status': 'error', 'message': 'Usuario ou CPF ja existe'}), 409
        finally:
            conn.close()
    return jsonify({'status': 'error', 'message': 'Erro sistema Linux'}), 500

# -----------------------------
# API: LOGIN/LOGOUT/PROFILE (APP)
# -----------------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    login_value = (data.get("login") or "").strip()
    password = (data.get("password") or "")
    hwid = (data.get("hwid") or "").strip()

    if not login_value or not password:
        return jsonify({"status": "error", "message": "Dados incompletos"}), 400

    conn = get_db()
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
        return jsonify({"status": "error", "message": "Conta bloqueada"}), 403
    if is_expired(u["expiration_date"] or ""):
        conn.close()
        return jsonify({"status": "error", "message": "Conta expirada"}), 403

    # Check HWID se ja existir
    if (u["hwid"] or "") and hwid and (u["hwid"] != hwid):
        conn.close()
        return jsonify({"status": "error", "message": "HWID nao bate"}), 403
    
    # Grava HWID se vazio
    if not (u["hwid"] or "") and hwid:
        conn.execute("UPDATE users SET hwid = ? WHERE uuid = ?", (hwid, u["uuid"]))
        conn.commit()

    token = str(uuid.uuid4())
    conn.execute("UPDATE users SET api_token = ?, token_created_at = ? WHERE uuid = ?", 
                 (token, datetime.now().isoformat(), u["uuid"]))
    conn.commit()
    
    # Recarrega user
    u2 = conn.execute("SELECT * FROM users WHERE uuid = ?", (u["uuid"],)).fetchone()
    conn.close()

    return jsonify({"status": "success", "token": token, "user": user_to_dict(u2)})

@app.route('/api/profile', methods=['GET'])
@api_token_required
def api_profile():
    return jsonify({"status": "success", "user": user_to_dict(request.user_row)})

@app.route('/api/logout', methods=['POST'])
@api_token_required
def api_logout():
    conn = get_db()
    conn.execute("UPDATE users SET api_token = NULL WHERE uuid = ?", (request.user_row["uuid"],))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Logout ok"})

# -----------------------------
# WEB ROUTES
# -----------------------------
@app.route('/api/online', methods=['GET'])
@login_required_api
def api_online():
    conn = get_db()
    users = conn.execute('SELECT username, limit_conn FROM users').fetchall()
    conn.close()
    data = []
    for u in users:
        qtd = sys_count_online(u['username'])
        data.append({'user': u['username'], 'online': qtd, 'limit': u['limit_conn']})
    return jsonify(data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET' and session.get('logged_in'):
        return redirect('/')
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user == 'admin' and pwd == 'admin':
            session['logged_in'] = True
            return redirect('/')
        return render_template('login.html', error="Acesso negado")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@login_required_page
def index():
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/action/kick/<username>')
@login_required_page
def action_kick(username):
    sys_kill_user(username)
    return redirect('/')

@app.route('/action/toggle/<uuid>')
@login_required_page
def action_toggle(uuid):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid,)).fetchone()
    if u:
        new_s = 0 if u['is_active'] else 1
        sys_toggle_user(u['username'], bool(new_s))
        conn.execute('UPDATE users SET is_active=? WHERE uuid=?', (new_s, uuid))
        conn.commit()
    conn.close()
    return redirect('/')

@app.route('/action/delete/<uuid>')
@login_required_page
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
