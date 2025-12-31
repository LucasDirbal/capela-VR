from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import logging
from datetime import datetime, timedelta, date

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

app = Flask(__name__)
app.secret_key = "chave_mestra_capela" 
DB_NAME = "capela.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        c = db.cursor()
        # Cria a tabela se ela não existir
        c.execute("""
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                login TEXT,
                senha TEXT DEFAULT '1234',
                role TEXT DEFAULT 'user',
                primeiro_login INTEGER DEFAULT 1,
                ordem INTEGER NOT NULL,
                ativo INTEGER DEFAULT 1
            )
        """)
        
        # Tenta adicionar as colunas uma por uma (caso a tabela já exista de versões antigas)
        colunas = [
            ("login", "TEXT"),
            ("senha", "TEXT DEFAULT '1234'"),
            ("role", "TEXT DEFAULT 'user'"),
            ("primeiro_login", "INTEGER DEFAULT 1")
        ]
        
        for nome_col, tipo_col in colunas:
            try:
                c.execute(f"ALTER TABLE pessoas ADD COLUMN {nome_col} {tipo_col}")
                logging.info(f"Coluna {nome_col} adicionada com sucesso.")
            except sqlite3.OperationalError:
                # Se a coluna já existir, o SQLite retorna erro, então apenas ignoramos
                pass

        c.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, data DATE NOT NULL, pessoa_id INTEGER NOT NULL)")
        db.commit()

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if session.get('role') != 'admin': 
        return redirect(url_for("login"))
        
    if request.method == "POST":
        # Coleta os dados do formulário
        nome_agenda = request.form["nome"].strip() # Nome que aparece na escala
        login_usuario = request.form["login"].strip().lower() # Login (sempre minúsculo)
        senha_usuario = request.form["senha"].strip()
        cargo = request.form["role"] # 'admin' ou 'user'
        
        with get_db() as db:
            c = db.cursor()
            # Pega a próxima ordem para a fila da agenda
            c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM pessoas")
            ordem = c.fetchone()[0]
            
            # Insere no banco. primeiro_login = 1 faz o sistema pedir troca de senha depois.
            c.execute("""
                INSERT INTO pessoas (nome, login, senha, role, primeiro_login, ordem) 
                VALUES (?, ?, ?, ?, 1, ?)
            """, (nome_agenda, login_usuario, senha_usuario, cargo, ordem))
            db.commit()
            
        logging.info(f"Admin cadastrou: {nome_agenda} | Login: {login_usuario} | Cargo: {cargo}")
        return redirect(url_for("pessoas"))
        
    return render_template("cadastrar.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Padronizamos para 'login_input' aqui
        login_input = request.form["nome"].strip().lower() 
        senha_input = request.form["senha"]
        
        logging.info(f"Tentativa de login: {login_input}")
        
        with get_db() as db:
            c = db.cursor()
            # Buscamos agora na coluna 'login'
            c.execute("SELECT * FROM pessoas WHERE LOWER(login) = ?", (login_input,))
            user = c.fetchone()
            
            if user and user['senha'] == senha_input:
                if user['primeiro_login'] == 1:
                    logging.info(f"Usuario {login_input} precisa mudar a senha.")
                    session['temp_user_id'] = user['id']
                    return render_template("mudar_senha.html", nome=user['nome'])
                
                session['user_id'] = user['id']
                session['nome'] = user['nome'] # Nome que vai aparecer na tela (ex: Lucas)
                session['role'] = user['role']
                logging.info(f"Login bem-sucedido: {login_input}")
                return redirect(url_for("agenda"))
        
        # Se chegou aqui, o login falhou
        logging.warning(f"Falha de login para: {login_input}")
        return "Login inválido! Verifique seu usuário e senha."
    
    return render_template("login.html")
@app.route("/atrasar", methods=["POST"])
def atrasar():
    if session.get('role') != 'admin': 
        return redirect(url_for("login"))

    dias = int(request.form.get("dias", 1))
    data_clicada = request.form.get("data_clicada") # Pegamos a data da linha onde clicou
    
    with get_db() as db:
        c = db.cursor()
        # O comando agora empurra todas as datas iguais ou maiores que a data selecionada
        c.execute("UPDATE agenda SET data = date(data, '+' || ? || ' day') WHERE data >= ?", (dias, data_clicada))
        db.commit()
    
    logging.info(f"Agenda atrasada em {dias} dias a partir de {data_clicada}.")
    return redirect(url_for("agenda"))

@app.route("/mudar_senha", methods=["POST"])
def mudar_senha():
    nova_senha = request.form["nova_senha"]
    user_id = session.get('temp_user_id')
    if user_id:
        with get_db() as db:
            c = db.cursor()
            c.execute("UPDATE pessoas SET senha = ?, primeiro_login = 0 WHERE id = ?", (nova_senha, user_id))
        logging.info(f"ID {user_id} alterou a senha padrão.")
        session.pop('temp_user_id', None)
        return "Senha alterada! <a href='/login'>Fazer Login</a>"
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    logging.info(f"Usuário {session.get('nome')} saiu.")
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def agenda():
    hoje = date.today().strftime("%Y-%m-%d")
    with get_db() as db:
        c = db.cursor()
        c.execute("""
            SELECT agenda.id, agenda.data, strftime('%d-%m-%Y', agenda.data) AS data_br, pessoas.nome
            FROM agenda JOIN pessoas ON pessoas.id = agenda.pessoa_id ORDER BY agenda.data
        """)
        dados = c.fetchall()
    return render_template("agenda.html", agenda=dados, hoje=hoje)

@app.route("/pessoas")
def pessoas():
    if session.get('role') != 'admin': 
        logging.warning(f"Acesso negado em /pessoas para {session.get('nome')}")
        return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT * FROM pessoas ORDER BY ordem")
        lista = c.fetchall()
    return render_template("pessoas.html", pessoas=lista)


@app.route("/remover_pessoa/<int:id>")
def remover_pessoa(id):
    if session.get('role') == 'admin':
        with get_db() as db:
            c = db.cursor()
            c.execute("DELETE FROM pessoas WHERE id = ?", (id,))
            c.execute("DELETE FROM agenda WHERE pessoa_id = ?", (id,))
        logging.info(f"Admin removeu ID {id}")
    return redirect(url_for("pessoas"))

@app.route("/editar_pessoa/<int:id>", methods=["GET", "POST"])
def editar_pessoa(id):
    if session.get('role') != 'admin': 
        return redirect(url_for("login"))
    
    with get_db() as db:
        c = db.cursor()
        if request.method == "POST":
            nome = request.form["nome"].strip()
            login_user = request.form["login"].strip().lower()
            role = request.form["role"]
            
            c.execute("""
                UPDATE pessoas 
                SET nome = ?, login = ?, role = ? 
                WHERE id = ?
            """, (nome, login_user, role, id))
            db.commit()
            logging.info(f"Admin editou ID {id}: {nome} ({login_user})")
            return redirect(url_for("pessoas"))
        
        # Busca os dados atuais para preencher o formulário
        c.execute("SELECT * FROM pessoas WHERE id = ?", (id,))
        pessoa = c.fetchone()
    
    return render_template("editar_pessoa.html", p=pessoa)

@app.route("/gerar")
def gerar_agenda():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("DELETE FROM agenda")
        c.execute("SELECT id FROM pessoas WHERE ativo = 1 ORDER BY ordem")
        lista = [p["id"] for p in c.fetchall()]
        if lista:
            data_corrida = date.today()
            for i in range(90):
                c.execute("INSERT INTO agenda (data, pessoa_id) VALUES (?, ?)", (data_corrida.strftime("%Y-%m-%d"), lista[i % len(lista)]))
                data_corrida += timedelta(days=1)
    logging.info("Agenda gerada para 90 dias.")
    return redirect(url_for("agenda"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)