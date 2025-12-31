#!/usr/bin/env python3
import os
import time
import uuid
from core import *
from datetime import datetime, timedelta

# Cores
C = "\033[1;36m" # Cyan
G = "\033[1;32m" # Green
R = "\033[1;31m" # Red
Y = "\033[1;33m" # Yellow
X = "\033[0m"    # Reset

def banner():
    os.system('clear')
    print(f"{C}======================================================================{X}")
    print(f"{C}                     VPSPACK SURREAL MANAGER v3.5                     {X}")
    print(f"{C}======================================================================{X}")

def input_nonempty(label: str) -> str:
    while True:
        v = input(label).strip()
        if v:
            return v
        print(f"{R}Campo obrigatório.{X}")

def input_int(label: str, default: int, min_value: int = 1) -> int:
    raw = input(f"{label} [{default}]: ").strip()
    if raw == "":
        return default
    try:
        n = int(raw)
        if n < min_value:
            raise ValueError
        return n
    except ValueError:
        print(f"{R}Valor inválido. Usando {default}.{X}")
        return default

def normalize_cpf(cpf: str) -> str:
    return "".join(ch for ch in cpf if ch.isdigit())

def edit_user():
    print(f"\n{C}--- Editar Usuário ---{X}")
    u_name = input_nonempty(" SSH User para editar: ")
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?', (u_name,)).fetchone()
    conn.close()

    if not user:
        print(f"{R}Usuário não encontrado.{X}")
        time.sleep(1.2)
        return

    print(f"\n{Y}Deixe em branco para manter o valor atual:{X}")
    
    # 1. Senha
    new_pass = input(f" Nova Senha [{user['password']}]: ").strip()
    
    # 2. Dados
    new_name = input(f" Novo Nome [{user['name'] or '-'}]: ").strip()
    new_email = input(f" Novo Email [{user['email'] or '-'}]: ").strip()
    new_hwid = input(f" Novo HWID [{user['hwid'] or '-'}]: ").strip()
    
    # 3. Limite
    raw_limit = input(f" Limite Conexões [{user['limit_conn']}]: ").strip()
    new_limit = int(raw_limit) if raw_limit else user['limit_conn']
    
    # 4. Validade
    print(f" Validade Atual: {user['expiration_date']}")
    raw_days = input(f" Renovar validade por quantos dias? (Vazio mantém): ").strip()

    # Processamento dos dados
    final_pass = new_pass if new_pass else user['password']
    final_name = new_name if new_name else user['name']
    final_email = new_email if new_email else user['email']
    final_hwid = new_hwid if new_hwid else user['hwid']
    
    if raw_days:
        try:
            d = int(raw_days)
            final_exp = (datetime.now() + timedelta(days=d)).strftime('%Y-%m-%d')
        except:
            final_exp = user['expiration_date']
    else:
        final_exp = user['expiration_date']

    # Atualiza no Linux se a senha mudou
    if new_pass:
        sys_change_password(u_name, final_pass)

    # Atualiza no Banco
    conn = get_db()
    try:
        conn.execute('''
            UPDATE users SET 
            password=?, name=?, email=?, hwid=?, limit_conn=?, expiration_date=?
            WHERE username=?
        ''', (final_pass, final_name, final_email, final_hwid, new_limit, final_exp, u_name))
        conn.commit()
        print(f"{G}Usuário {u_name} atualizado com sucesso!{X}")
    except Exception as e:
        print(f"{R}Erro ao atualizar: {e}{X}")
    finally:
        conn.close()
    time.sleep(1.5)

def main():
    init_db()
    while True:
        banner()
        conn = get_db()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()

        # Cabeçalho formatado
        print(f" {'SSH USER':<14} {'LIMIT':<8} {'EXPIRAÇÃO':<12} {'NOME':<18} {'STATUS'}")
        print(f" {C}" + "-"*72 + f"{X}")

        for u in users:
            on = sys_count_online(u['username'])
            on_str = f"{on}/{u['limit_conn']}"
            if on >= int(u['limit_conn']): on_str = f"{R}{on_str}{X}"
            else: on_str = f"{G}{on_str}{X}"

            st = f"{G}ATIVO{X}" if u['is_active'] else f"{R}BLOQ {X}"
            exp_date = u['expiration_date']
            name = (u['name'] or "-")[:18]
            
            print(f" {u['username']:<14} {on_str:<17} {exp_date:<12} {name:<18} {st}")

        print(f"\n {Y}[1]{X} Criar Usuario")
        print(f" {Y}[2]{X} Deletar Usuario")
        print(f" {Y}[3]{X} Expulsar (Kick)")
        print(f" {Y}[4]{X} Bloquear / Desbloquear")
        print(f" {Y}[5]{X} Editar Usuario (Senha/Limite/Data)")
        print(f" {Y}[0]{X} Sair")

        op = input(f"\n {C}>> {X}").strip()

        if op == '1':
            print(f"\n{C}--- Criar Usuário ---{X}")
            username = input_nonempty(" SSH User: ")
            password = input_nonempty(" Senha: ")
            name = input(" Nome: ").strip()
            cpf = normalize_cpf(input_nonempty(" CPF: "))
            limit_conn = input_int(" Limite conexões", default=1)
            days = input_int(" Dias validade", default=30)

            if len(cpf) < 11:
                print(f"{R}CPF inválido.{X}"); time.sleep(1.2); continue

            if sys_create_user(username, password):
                exp = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d')
                conn = get_db()
                try:
                    conn.execute('''
                        INSERT INTO users (uuid, username, password, name, cpf, limit_conn, expiration_date, is_active)
                        VALUES (?,?,?,?,?,?,?,?)
                    ''', (str(uuid.uuid4()), username, password, name, cpf, int(limit_conn), exp, 1))
                    conn.commit()
                    print(f"{G}Criado com sucesso!{X}")
                except:
                    sys_delete_user(username)
                    print(f"{R}Erro no banco de dados.{X}")
                finally:
                    conn.close()
                time.sleep(1.4)

        elif op == '2':
            u = input_nonempty(" SSH User para deletar: ")
            sys_delete_user(u)
            conn = get_db()
            conn.execute('DELETE FROM users WHERE username=?', (u,))
            conn.commit()
            conn.close()
            print(f"{R}Deletado!{X}"); time.sleep(1.2)

        elif op == '3':
            u = input_nonempty(" SSH User para expulsar: ")
            ok = sys_kill_user(u)
            print(f"{G}Expulso!{X}" if ok else f"{R}Falha.{X}"); time.sleep(1.1)

        elif op == '4':
            u = input_nonempty(" SSH User para Bloq/Ativar: ")
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE username=?', (u,)).fetchone()
            if user:
                new_status = 0 if user['is_active'] else 1
                if sys_toggle_user(u, bool(new_status)):
                    conn.execute('UPDATE users SET is_active=? WHERE username=?', (new_status, u))
                    conn.commit()
                    print(f"{G}Status: {'ATIVO' if new_status else 'BLOQ'}!{X}")
            else: print(f"{Y}Não encontrado.{X}")
            conn.close(); time.sleep(1.2)

        elif op == '5':
            edit_user()

        elif op == '0':
            break

if __name__ == '__main__':
    main()
