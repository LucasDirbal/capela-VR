from flask import Flask, render_template, request, redirect, url_for, session, flash
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS pessoas (
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
        c.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, data DATE NOT NULL, pessoa_id INTEGER NOT NULL)")
        db.commit()

# --- ROTA PRINCIPAL (AGENDA + PAINEL CAPELA ✝️) ---
@app.route("/")
def agenda():
    hoje_dt = date.today()
    hoje_str = hoje_dt.strftime("%Y-%m-%d")
    dias_faltando = None
    proxima_data_obj = None

    with get_db() as db:
        c = db.cursor()
        
        # Busca a agenda. O dia de entrega é a data da agenda + 1 dia
        c.execute("""
            SELECT 
                agenda.id, 
                agenda.data, 
                strftime('%d-%m-%Y', agenda.data) AS data_recebeu,
                strftime('%d-%m-%Y', date(agenda.data, '+1 day')) AS data_entrega,
                pessoas.nome, 
                agenda.pessoa_id
            FROM agenda 
            JOIN pessoas ON pessoas.id = agenda.pessoa_id 
            ORDER BY agenda.data
        """)
        dados = c.fetchall()

        if session.get('user_id'):
            c.execute("""
                SELECT data FROM agenda 
                WHERE pessoa_id = ? AND data >= ? 
                ORDER BY data ASC LIMIT 1
            """, (session['user_id'], hoje_str))
            res = c.fetchone()
            if res:
                proxima_data_obj = datetime.strptime(res['data'], "%Y-%m-%d").date()
                dias_faltando = (proxima_data_obj - hoje_dt).days

    return render_template("agenda.html", agenda=dados, hoje=hoje_str, dias_faltando=dias_faltando, proxima_data=proxima_data_obj)

# --- SISTEMA DE LOGIN E SENHA ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form["nome"].strip().lower()
        senha_input = request.form["senha"]
        
        with get_db() as db:
            c = db.cursor()
            c.execute("SELECT * FROM pessoas WHERE LOWER(login) = ?", (login_input,))
            user = c.fetchone()
            
            if user and user['senha'] == senha_input:
                if user['primeiro_login'] == 1:
                    session['temp_user_id'] = user['id']
                    return render_template("mudar_senha.html", nome=user['nome'])
                
                session['user_id'] = user['id']
                session['nome'] = user['nome']
                session['role'] = user['role']
                return redirect(url_for("agenda"))
        
        flash("Usuário ou senha incorretos.", "danger")
    return render_template("login.html")

@app.route("/mudar_senha", methods=["POST"])
def mudar_senha():
    nova_senha = request.form["nova_senha"]
    user_id = session.get('temp_user_id')
    if user_id:
        with get_db() as db:
            c = db.cursor()
            c.execute("UPDATE pessoas SET senha = ?, primeiro_login = 0 WHERE id = ?", (nova_senha, user_id))
            db.commit()
        session.pop('temp_user_id', None)
        flash("Senha alterada com sucesso! Faça login.", "success")
        return redirect(url_for("login"))
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- GESTÃO DA AGENDA (ATRASAR / GERAR) ---
@app.route("/atrasar", methods=["POST"])
def atrasar():
    if not session.get('user_id'): return redirect(url_for("login"))
    dias = int(request.form.get("dias", 1))
    data_clicada = request.form.get("data_clicada")
    with get_db() as db:
        c = db.cursor()
        c.execute("UPDATE agenda SET data = date(data, '+' || ? || ' day') WHERE data >= ?", (dias, data_clicada))
        db.commit()
    flash("Agenda atualizada!", "success")
    return redirect(url_for("agenda"))

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
                c.execute("INSERT INTO agenda (data, pessoa_id) VALUES (?, ?)", 
                          (data_corrida.strftime("%Y-%m-%d"), lista[i % len(lista)]))
                data_corrida += timedelta(days=1)
            db.commit()
    flash("Agenda gerada para os próximos 90 dias!", "success")
    return redirect(url_for("agenda"))

# --- GESTÃO DE PESSOAS (EQUIPA) ---
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
        nome = request.form["nome"].strip()
        login_user = request.form["login"].strip().lower()
        senha = request.form["senha"].strip()
        role = request.form["role"]
        with get_db() as db:
            c = db.cursor()
            c.execute("SELECT id FROM pessoas WHERE login = ?", (login_user,))
            if c.fetchone():
                flash("Este login já existe!", "danger")
                return redirect(url_for("cadastrar"))
            c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM pessoas")
            ordem = c.fetchone()[0]
            c.execute("INSERT INTO pessoas (nome, login, senha, role, primeiro_login, ordem) VALUES (?,?,?,?,?,?)",
                      (nome, login_user, senha, role, 1, ordem))
            db.commit()
        return redirect(url_for("pessoas"))
    return render_template("cadastrar.html")

@app.route("/editar_pessoa/<int:id>", methods=["GET", "POST"])
def editar_pessoa(id):
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        if request.method == "POST":
            c.execute("UPDATE pessoas SET nome=?, login=?, role=? WHERE id=?", 
                      (request.form["nome"], request.form["login"].lower(), request.form["role"], id))
            db.commit()
            return redirect(url_for("pessoas"))
        c.execute("SELECT * FROM pessoas WHERE id=?", (id,))
        pessoa = c.fetchone()
    return render_template("editar_pessoa.html", p=pessoa)

@app.route("/remover_pessoa/<int:id>")
def remover_pessoa(id):
    if session.get('role') == 'admin':
        with get_db() as db:
            c = db.cursor()
            c.execute("DELETE FROM pessoas WHERE id = ?", (id,))
            c.execute("DELETE FROM agenda WHERE pessoa_id = ?", (id,))
            db.commit()
    return redirect(url_for("pessoas"))

@app.route("/mover_pessoa/<int:id>/<direcao>")
def mover_pessoa(id, direcao):
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT ordem FROM pessoas WHERE id = ?", (id,))
        p_atual = c.fetchone()
        if not p_atual: return redirect(url_for("pessoas"))
        
        ordem_atual = p_atual['ordem']
        if direcao == "subir":
            c.execute("SELECT id, ordem FROM pessoas WHERE ordem < ? ORDER BY ordem DESC LIMIT 1", (ordem_atual,))
        else:
            c.execute("SELECT id, ordem FROM pessoas WHERE ordem > ? ORDER BY ordem ASC LIMIT 1", (ordem_atual,))
        
        vizinho = c.fetchone()
        if vizinho:
            c.execute("UPDATE pessoas SET ordem = ? WHERE id = ?", (vizinho['ordem'], id))
            c.execute("UPDATE pessoas SET ordem = ? WHERE id = ?", (ordem_atual, vizinho['id']))
            db.commit()
    return redirect(url_for("pessoas"))

@app.route("/definir_posicao", methods=["GET", "POST"])
def definir_posicao():
    # Segurança: Apenas admin acessa
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
    
    with get_db() as db:
        c = db.cursor()
        
        if request.method == "POST":
            pessoa_id = request.form.get("pessoa_id")
            data_inicio = request.form.get("data_inicio")
            
            if pessoa_id and data_inicio:
                # 1. Limpa a agenda atual para evitar conflitos
                c.execute("DELETE FROM agenda")
                
                # 2. Busca todas as pessoas ativas a partir da ordem da pessoa selecionada
                # (Isso faz com que a escala siga a sequência correta a partir dela)
                c.execute("SELECT id FROM pessoas WHERE ativo = 1 ORDER BY ordem")
                lista_pessoas = [p['id'] for p in c.fetchall()]
                
                # Reorganiza a lista para começar pela pessoa escolhida
                idx = lista_pessoas.index(int(pessoa_id))
                lista_ordenada = lista_pessoas[idx:] + lista_pessoas[:idx]
                
                # 3. Gera a nova agenda por 90 dias
                data_corrida = datetime.strptime(data_inicio, "%Y-%m-%d").date()
                for i in range(90):
                    p_id = lista_ordenada[i % len(lista_ordenada)]
                    c.execute("INSERT INTO agenda (data, pessoa_id) VALUES (?, ?)", 
                              (data_corrida.strftime("%Y-%m-%d"), p_id))
                    data_corrida += timedelta(days=1)
                
                db.commit()
                flash("Posição da Capela atualizada com sucesso!", "success")
                return redirect(url_for("agenda"))

        # Busca lista de pessoas para o dropdown do formulário
        c.execute("SELECT id, nome FROM pessoas WHERE ativo = 1 ORDER BY nome")
        pessoas_lista = c.fetchall()
        
    return render_template("definir_posicao.html", pessoas=pessoas_lista)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)