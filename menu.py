
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

def main():
    init_db()
    while True:
        banner()
        conn = get_db()
        users = conn.execute('SELECT * FROM users').fetchall()
        conn.close()

        print(f" {'USER':<15} {'SENHA':<10} {'ONLINE':<10} {'STATUS'}")
        print(f" {C}" + "-"*45 + f"{X}")

        for u in users:
            # Monitoramento no Terminal
            on = sys_count_online(u['username'])
            on_str = f"{on}/{u['limit_conn']}"
            if on >= u['limit_conn']: on_str = f"{R}{on_str}{X}"
            else: on_str = f"{G}{on_str}{X}"

            st = f"{G}ATIVO{X}" if u['is_active'] else f"{R}BLOQ {X}"
            print(f" {u['username']:<15} {u['password']:<10} {on_str:<19} {st}")
        
        print(f"\n {Y}[1]{X} Criar Usuario")
        print(f" {Y}[2]{X} Deletar Usuario")
        print(f" {Y}[3]{X} Expulsar (Kick)")
        print(f" {Y}[0]{X} Sair")

        op = input(f"\n {C}>> {X}")

        if op == '1':
            u = input(" User: ")
            p = input(" Pass: ")
            l = input(" Limit: ")
            d = input(" Dias: ")
            if sys_create_user(u, p):
                exp = (datetime.now() + timedelta(days=int(d))).strftime('%Y-%m-%d')
                conn = get_db()
                conn.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', 
                             (str(uuid.uuid4()), u, p, l, exp, 1))
                conn.commit()
                conn.close()
                print(f"{G}Criado!{X}")
                time.sleep(1)
        elif op == '2':
            u = input(" User para deletar: ")
            # Busca UUID pelo nome
            conn = get_db()
            res = conn.execute('SELECT uuid FROM users WHERE username=?', (u,)).fetchone()
            conn.close()
            if res:
                sys_delete_user(u)
                conn = get_db()
                conn.execute('DELETE FROM users WHERE username=?', (u,))
                conn.commit()
                conn.close()
                print(f"{R}Deletado!{X}")
            time.sleep(1)
        elif op == '3':
            u = input(" User para expulsar: ")
            sys_kill_user(u)
            print("Expulso!")
            time.sleep(1)
        elif op == '0': break

if __name__ == '__main__':
    main()
