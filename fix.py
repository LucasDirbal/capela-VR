import sqlite3

def consertar():
    conn = sqlite3.connect('capela.db')
    c = conn.cursor()
    
    # Este comando atualiza o ID 1 com todos os campos necessários
    # Usando aspas triplas para não ter erro de sintaxe
    sql = """
    UPDATE pessoas 
    SET login = 'lucas', 
        nome = 'Lucas', 
        senha = '2602dirbal', 
        role = 'admin', 
        primeiro_login = 0 
    WHERE id = 1
    """
    
    try:
        c.execute(sql)
        conn.commit()
        print("-------------------------------")
        print("SUCESSO: Usuario ID 1 atualizado!")
        print("Login: lucas")
        print("Senha: 2602dirbal")
        print("-------------------------------")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    consertar()