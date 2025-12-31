from flask import Flask, render_template, request, redirect, session, jsonify
from core import *
import uuid

app = Flask(__name__)
app.secret_key = 'CHAVE_ULTRA_SECRETA_MUDE_ISSO'

init_db()

# --- API PUBLICA (Criação Completa) ---
@app.route('/api/create', methods=['POST'])
def api_create():
    data = request.json
    
    # Dados obrigatórios
    username = data.get('username') # SSH User
    password = data.get('password')
    cpf = data.get('cpf')
    
    # Dados opcionais
    name = data.get('name', '')
    email = data.get('email', '')
    hwid = data.get('hwid', '')
    limit = data.get('limit', 1)
    days = data.get('days', 30)

    if not username or not password or not cpf:
        return jsonify({'status': 'error', 'message': 'Campos SSH User, Senha e CPF são obrigatórios'}), 400

    # Cria no Linux (Apenas o usuário SSH existe no Linux)
    if sys_create_user(username, password):
        # Salva no Banco com dados completos
        expiry = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d')
        conn = get_db()
        try:
            conn.execute('''
                INSERT INTO users (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active) 
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (str(uuid.uuid4()), username, password, name, cpf, email, hwid, limit, expiry, 1))
            conn.commit()
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Erro: Usuário ou CPF já existe'}), 409
        finally:
            conn.close()
    
    return jsonify({'status': 'error', 'message': 'Erro ao criar no sistema Linux'}), 500

@app.route('/api/online', methods=['GET'])
def api_online():
    if not session.get('logged_in'): return jsonify([])
    conn = get_db()
    users = conn.execute('SELECT username, limit_conn FROM users').fetchall()
    conn.close()
    
    data = []
    for u in users:
        qtd = sys_count_online(u['username'])
        data.append({'user': u['username'], 'online': qtd, 'limit': u['limit_conn']})
    return jsonify(data)

# --- ROTAS DO PAINEL ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cpf = request.form['username'] # O form envia name='username' mas tratamos como CPF ou ADMIN
        password = request.form['password']
        
        # Login Admin Master
        if cpf == 'admin' and password == 'admin':
            session['logged_in'] = True
            return redirect('/')
            
        # Login Cliente (Pelo CPF)
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE cpf = ? AND password = ?', (cpf, password)).fetchone()
        conn.close()
        
        if user:
            # Se quiser fazer painel pro cliente no futuro, redireciona aqui.
            # Por enquanto, só admin entra no painel de gestão.
            return render_template('login.html', error="Painel apenas para Admin (por enquanto)")
        
        return render_template('login.html', error="CPF ou Senha incorretos")

    return render_template('login.html')

@app.route('/')
def index():
    if not session.get('logged_in'): return redirect('/login')
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('index.html', users=users)

@app.route('/action/kick/<username>')
def action_kick(username):
    if not session.get('logged_in'): return redirect('/login')
    sys_kill_user(username)
    return redirect('/')

@app.route('/action/toggle/<uuid>')
def action_toggle(uuid):
    if not session.get('logged_in'): return redirect('/login')
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid,)).fetchone()
    
    new_status = not u['is_active']
    sys_toggle_user(u['username'], new_status)
    conn.execute('UPDATE users SET is_active=? WHERE uuid=?', (new_status, uuid))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/action/delete/<uuid>')
def action_delete(uuid):
    if not session.get('logged_in'): return redirect('/login')
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE uuid=?', (uuid,)).fetchone()
    sys_delete_user(u['username'])
    conn.execute('DELETE FROM users WHERE uuid=?', (uuid,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
