from flask import Flask, render_template, request, redirect, session, jsonify
from functools import wraps
from core import *
import uuid

app = Flask(__name__)
app.secret_key = 'CHAVE_ULTRA_SECRETA_MUDE_ISSO_AGORA'

init_db()

# --- DECORATOR DE SEGURANÇA ---
# Protege apenas rotas críticas, deixando a API de criação 'semi-aberta'
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/') and not request.path == '/api/create':
                return jsonify({'status': 'error', 'message': 'Acesso Negado'}), 401
            if not request.path.startswith('/api/'):
                return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# --- API DE CRIAÇÃO (Lógica Híbrida) ---
@app.route('/api/create', methods=['POST'])
def api_create():
    data = request.json
    
    # Dados obrigatórios
    username = data.get('username')
    password = data.get('password')
    cpf = data.get('cpf')
    
    # Dados opcionais
    name = data.get('name', '')
    email = data.get('email', '')
    hwid = data.get('hwid', '')

    if not username or not password or not cpf:
        return jsonify({'status': 'error', 'message': 'Campos SSH User, Senha e CPF são obrigatórios'}), 400

    # --- LÓGICA DE PERMISSÃO ---
    if session.get('logged_in'):
        # ADMIN CRIANDO: Aceita os valores que o Admin digitar
        status_ativo = 1
        dias_validade = int(data.get('days', 30))
        limite_conn = int(data.get('limit', 1))
    else:
        # APP/PÚBLICO CRIANDO: Força bloqueio e validade zero
        status_ativo = 0     # Cria bloqueado
        dias_validade = 0    # Validade zerada
        limite_conn = 1      # Limite padrão

    # Cria no Linux
    if sys_create_user(username, password):
        # Se for público/bloqueado, já tranca no Linux imediatamente
        if status_ativo == 0:
            sys_toggle_user(username, False)

        # Salva no Banco
        expiry = (datetime.now() + timedelta(days=dias_validade)).strftime('%Y-%m-%d')
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active) 
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (str(uuid.uuid4()), username, password, name, cpf, email, hwid, limite_conn, expiry, status_ativo))
            conn.commit()
            
            # Mensagem de sucesso diferente para Admin e Público
            msg = 'Usuário criado com sucesso!' if status_ativo else 'Cadastro realizado! Aguarde aprovação.'
            return jsonify({'status': 'success', 'message': msg})
            
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Usuário ou CPF já existe'}), 409
        finally:
            conn.close()
    
    return jsonify({'status': 'error', 'message': 'Erro ao criar no sistema Linux'}), 500

# --- DEMAIS ROTAS (PROTEGIDAS) ---

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form['username']
        password = request.form['password']
        
        if login_input == 'admin' and password == 'admin':
            session['logged_in'] = True
            return redirect('/')
            
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE cpf = ? AND password = ?', (login_input, password)).fetchone()
        conn.close()
        
        # Cliente tenta logar
        if user:
            if not user['is_active']:
                return render_template('login.html', error="Sua conta está bloqueada/pendente.")
            return render_template('login.html', error="Painel do Cliente em Breve")
        
        return render_template('login.html', error="Dados inválidos")

    return render_template('login.html')

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
    
    new_status = not u['is_active']
    sys_toggle_user(u['username'], new_status)
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
