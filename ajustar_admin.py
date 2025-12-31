import sqlite3

def reset_admin():
    try:
        # Conecta ao banco de dados
        conn = sqlite3.connect('capela.db')
        c = conn.cursor()

        # Comando SQL:
        # INSERT OR REPLACE tenta inserir o ID 1. Se já existir, ele substitui os dados.
        sql = """
        INSERT OR REPLACE INTO pessoas (id, nome, senha, role, primeiro_login, ordem) 
        VALUES (1, 'lucas', '2602dirbal', 'admin', 0, 1)
        """
        
        c.execute(sql)
        conn.commit()
        
        print("-" * 30)
        print("SUCESSO!")
        print("Usuário: lucas")
        print("Senha:  2602dirbal")
        print("Cargo:  admin")
        print("-" * 30)

    except Exception as e:
        print(f"Erro ao acessar o banco: {e}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_admin()