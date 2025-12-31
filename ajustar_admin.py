import sqlite3

def reset_total():
    conn = sqlite3.connect("capela.db")
    c = conn.cursor()
    
    # Apaga as tabelas para garantir do zero
    c.execute("DROP TABLE IF EXISTS pessoas")
    c.execute("DROP TABLE IF EXISTS agenda")
    
    # Cria a tabela de pessoas com a estrutura correta
    c.execute("""
        CREATE TABLE pessoas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            login TEXT UNIQUE,
            senha TEXT DEFAULT '1234',
            role TEXT DEFAULT 'user',
            primeiro_login INTEGER DEFAULT 1,
            ordem INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1
        )
    """)
    
    # Cria a tabela de agenda com o campo STATUS
    c.execute("""
        CREATE TABLE agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            data DATE NOT NULL, 
            pessoa_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pendente'
        )
    """)
    
    # Insere o ADMIN (ajuste o login e senha se quiser)
    # Importante: ordem 0 para o admin
    c.execute("""
        INSERT INTO pessoas (nome, login, senha, role, ordem, ativo) 
        VALUES ('Administrador', 'admin', '1234', 'admin', 0, 1)
    """)
    
    conn.commit()
    conn.close()
    print("✅ Banco resetado e Admin criado (Login: admin / Senha: 1234)")

if __name__ == "__main__":
    reset_total()