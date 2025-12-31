from flask import Flask, render_template, request, redirect, session, jsonify
from core import *
import uuid

app = Flask(__name__)
app.secret_key = 'CHAVE_ULTRA_SECRETA_MUDE_ISSO'

init_db()

# --- API PUBLICA (Para Bots/Integrações) ---
@app.route('/api/create', methods=['POST'])
def api_create():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    limit = data.get('limit', 1)
    days = data.get('days', 30)

    # Cria no Linux
    if sys_create_user(username, password):
        # Salva no Banco
        expiry = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d')
        conn = get_db()
        try:
            conn.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',
                         (str(uuid.uuid4()), username, password, limit, expiry, 1))
            conn.commit()
            return jsonify({'status': 'success', 'data': {'username': username, 'exp': expiry}})
        except:
            return jsonify({'status': 'error', 'message': 'User exists'}), 409
        finally:
            conn.close()
    return jsonify({'status': 'error', 'message': 'System error'}), 500

@app.route('/api/online', methods=['GET'])
def api_online():
    # Rota leve para o painel ficar consultando
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
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect('/')
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
