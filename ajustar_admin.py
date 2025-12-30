import sqlite3

conn = sqlite3.connect("capela.db")
c = conn.cursor()

# Vamos procurar o usuário que tem a role 'admin' e atualizar o nome e a senha dele
c.execute("""
    UPDATE pessoas 
    SET nome = ?, senha = ? 
    WHERE role = 'admin'
""", ('Lucas', '2602dirbal'))

conn.commit()

if c.rowcount > 0:
    print("Sucesso! Agora você deve logar como Lucas.")
else:
    print("Erro: Nenhum usuário administrador encontrado para atualizar.")

conn.close()