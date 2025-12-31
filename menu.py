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
    print(f"{C}========================================{X}")
    print(f"{C}       VPSPACK SURREAL MANAGER v3.0     {X}")
    print(f"{C}========================================{X}")

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

def main():
    init_db()
    while True:
        banner()
        conn = get_db()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()

        # Cabeçalho mais completo
        print(f" {'SSH USER':<14} {'CPF':<12} {'NOME':<18} {'ONLINE':<10} {'STATUS'}")
        print(f" {C}" + "-"*72 + f"{X}")

        for u in users:
            on = sys_count_online(u['username'])
            on_str = f"{on}/{u['limit_conn']}"
            if on >= int(u['limit_conn']): on_str = f"{R}{on_str}{X}"
            else: on_str = f"{G}{on_str}{X}"

            st = f"{G}ATIVO{X}" if u['is_active'] else f"{R}BLOQ {X}"

            cpf = (u['cpf'] or "")[:11]
            name = (u['name'] or "-")[:18]
            print(f" {u['username']:<14} {cpf:<12} {name:<18} {on_str:<12} {st}")

        print(f"\n {Y}[1]{X} Criar Usuario (Completo)")
        print(f" {Y}[2]{X} Deletar Usuario")
        print(f" {Y}[3]{X} Expulsar (Kick)")
        print(f" {Y}[4]{X} Bloquear / Desbloquear")
        print(f" {Y}[0]{X} Sair")

        op = input(f"\n {C}>> {X}").strip()

        if op == '1':
            print(f"\n{C}--- Criar Usuário Completo ---{X}")
            username = input_nonempty(" SSH User: ")
            password = input_nonempty(" Senha: ")

            name = input(" Nome (opcional): ").strip()
            cpf = normalize_cpf(input_nonempty(" CPF (obrigatório): "))
            email = input(" Email (opcional): ").strip()
            hwid = input(" HWID (opcional): ").strip()

            limit_conn = input_int(" Limite conexões", default=1, min_value=1)
            days = input_int(" Dias validade", default=30, min_value=1)

            # valida cpf mínimo
            if len(cpf) < 11:
                print(f"{R}CPF inválido (precisa 11 dígitos). Cancelado.{X}")
                time.sleep(1.4)
                continue

            # Cria usuario Linux (SSH)
            if sys_create_user(username, password):
                exp = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d')

                conn = get_db()
                try:
                    conn.execute('''
                        INSERT INTO users
                        (uuid, username, password, name, cpf, email, hwid, limit_conn, expiration_date, is_active)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        str(uuid.uuid4()),
                        username,
                        password,
                        name,
                        cpf,
                        email,
                        hwid,
                        int(limit_conn),
                        exp,
                        1
                    ))
                    conn.commit()
                    print(f"{G}Criado com sucesso!{X}")
                except Exception as e:
                    # Se falhar, apaga usuário Linux criado para não ficar lixo
                    try:
                        sys_delete_user(username)
                    except:
                        pass
                    print(f"{R}Erro ao salvar no banco (usuário/CPF duplicado?).{X}")
                finally:
                    conn.close()

                time.sleep(1.4)
            else:
                print(f"{R}Erro ao criar no sistema Linux.{X}")
                time.sleep(1.4)

        elif op == '2':
            u = input_nonempty(" SSH User para deletar: ")
            conn = get_db()
            res = conn.execute('SELECT username FROM users WHERE username=?', (u,)).fetchone()
            conn.close()
            if res:
                sys_delete_user(u)
                conn = get_db()
                conn.execute('DELETE FROM users WHERE username=?', (u,))
                conn.commit()
                conn.close()
                print(f"{R}Deletado!{X}")
            else:
                print(f"{Y}Usuário não encontrado.{X}")
            time.sleep(1.2)

        elif op == '3':
            u = input_nonempty(" SSH User para expulsar: ")
            ok = sys_kill_user(u)
            print(f"{G}Expulso!{X}" if ok else f"{R}Falha ao expulsar.{X}")
            time.sleep(1.1)

        elif op == '4':
            u = input_nonempty(" SSH User para Bloq/Ativar: ")
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE username=?', (u,)).fetchone()
            if not user:
                conn.close()
                print(f"{Y}Usuário não encontrado.{X}")
                time.sleep(1.2)
                continue

            new_status = 0 if user['is_active'] else 1
            ok = sys_toggle_user(user['username'], bool(new_status))
            if ok:
                conn.execute('UPDATE users SET is_active=? WHERE username=?', (new_status, u))
                conn.commit()
                print(f"{G}Status alterado para {'ATIVO' if new_status else 'BLOQ'}!{X}")
            else:
                print(f"{R}Falha ao alterar status no sistema.{X}")
            conn.close()
            time.sleep(1.2)

        elif op == '0':
            break

if __name__ == '__main__':
    main()
