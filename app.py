from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta, date

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
        c.execute("""
            CREATE TABLE IF NOT EXISTS pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                senha TEXT DEFAULT '1234',
                role TEXT DEFAULT 'user',
                primeiro_login INTEGER DEFAULT 1,
                ordem INTEGER NOT NULL,
                ativo INTEGER DEFAULT 1
            )
        """)
        # Atualização de colunas para bancos antigos
        try:
            c.execute("ALTER TABLE pessoas ADD COLUMN senha TEXT DEFAULT '1234'")
            c.execute("ALTER TABLE pessoas ADD COLUMN role TEXT DEFAULT 'user'")
            c.execute("ALTER TABLE pessoas ADD COLUMN primeiro_login INTEGER DEFAULT 1")
        except: pass

        c.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, data DATE NOT NULL, pessoa_id INTEGER NOT NULL)")
        
        # Garante que o Lucas seja o Admin mestre (sempre em minúsculo no banco)
        c.execute("SELECT * FROM pessoas WHERE role = 'admin'")
        if not c.fetchone():
            c.execute("INSERT INTO pessoas (nome, senha, role, primeiro_login, ordem) VALUES (?,?,?,?,?)",
                      ('lucas', '2602dirbal', 'admin', 0, 1))
        else:
            # Atualiza caso o admin já exista mas com outro nome/senha
            c.execute("UPDATE pessoas SET nome = ?, senha = ? WHERE role = 'admin'", ('lucas', '2602dirbal'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # .lower() garante que "Lucas" ou "LUCAS" vire "lucas"
        nome_input = request.form["nome"].strip().lower()
        senha_input = request.form["senha"]
        
        with get_db() as db:
            c = db.cursor()
            c.execute("SELECT * FROM pessoas WHERE LOWER(nome) = ?", (nome_input,))
            user = c.fetchone()
            
            if user and user['senha'] == senha_input:
                if user['primeiro_login'] == 1:
                    session['temp_user_id'] = user['id']
                    return render_template("mudar_senha.html", nome=user['nome'])
                
                session['user_id'] = user['id']
                session['nome'] = user['nome']
                session['role'] = user['role']
                return redirect(url_for("agenda"))
        return "Login inválido! Tente novamente."
    return render_template("login.html")

@app.route("/mudar_senha", methods=["POST"])
def mudar_senha():
    nova_senha = request.form["nova_senha"]
    user_id = session.get('temp_user_id')
    if user_id:
        with get_db() as db:
            c = db.cursor()
            c.execute("UPDATE pessoas SET senha = ?, primeiro_login = 0 WHERE id = ?", (nova_senha, user_id))
        session.pop('temp_user_id', None)
        return "Senha alterada! <a href='/login'>Clique aqui para logar</a>"
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
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
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT * FROM pessoas ORDER BY ordem")
        lista = c.fetchall()
    return render_template("pessoas.html", pessoas=lista)

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    if request.method == "POST":
        nome = request.form["nome"].strip().lower() # Salva sempre em minúsculo
        with get_db() as db:
            c = db.cursor()
            c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM pessoas")
            ordem = c.fetchone()[0]
            c.execute("INSERT INTO pessoas (nome, ordem) VALUES (?, ?)", (nome, ordem))
        return redirect(url_for("pessoas"))
    return render_template("cadastrar.html")

@app.route("/remover_pessoa/<int:id>")
def remover_pessoa(id):
    if session.get('role') == 'admin':
        with get_db() as db:
            c = db.cursor()
            c.execute("DELETE FROM pessoas WHERE id = ?", (id,))
            c.execute("DELETE FROM agenda WHERE pessoa_id = ?", (id,))
    return redirect(url_for("pessoas"))

@app.route("/mover_pessoa/<int:id>/<direcao>")
def mover_pessoa(id, direcao):
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT ordem FROM pessoas WHERE id = ?", (id,))
        ordem_atual = c.fetchone()['ordem']
        if direcao == "subir":
            c.execute("SELECT id, ordem FROM pessoas WHERE ordem < ? ORDER BY ordem DESC LIMIT 1", (ordem_atual,))
        else:
            c.execute("SELECT id, ordem FROM pessoas WHERE ordem > ? ORDER BY ordem ASC LIMIT 1", (ordem_atual,))
        outro = c.fetchone()
        if outro:
            c.execute("UPDATE pessoas SET ordem = ? WHERE id = ?", (outro['ordem'], id))
            c.execute("UPDATE pessoas SET ordem = ? WHERE id = ?", (ordem_atual, outro['id']))
    return redirect(url_for("pessoas"))

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
    return redirect(url_for("agenda"))

@app.route("/atrasar", methods=["POST"])
def atrasar():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    dias = int(request.form["dias"])
    hoje = date.today().strftime("%Y-%m-%d")
    with get_db() as db:
        c = db.cursor()
        c.execute("UPDATE agenda SET data = date(data, '+' || ? || ' day') WHERE data >= ?", (dias, hoje))
    return redirect(url_for("agenda"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)