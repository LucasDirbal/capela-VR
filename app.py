from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import logging
from datetime import datetime, timedelta, date

# --- CONFIGURAÇÃO ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.secret_key = "chave_mestra_capela" 
DB_NAME = "capela.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# --- INICIALIZAÇÃO DO BANCO ---
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                data DATE NOT NULL, 
                pessoa_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pendente'
            )
        """)
        # Garante que a coluna status exista (caso o banco já tenha sido criado antes)
        try:
            c.execute("ALTER TABLE agenda ADD COLUMN status TEXT DEFAULT 'pendente'")
        except:
            pass
        db.commit()

# --- ROTA PRINCIPAL (AGENDA) ---
@app.route("/")
def agenda():
    hoje_dt = date.today()
    hoje_str = hoje_dt.strftime("%Y-%m-%d")
    dias_faltando = None
    proxima_data_obj = None
    status_hoje = 'pendente'

    with get_db() as db:
        c = db.cursor()
        
        # --- PARTE QUE VOCÊ ESTAVA TENTANDO INTEGRAR ---
        # Buscamos todos os campos da agenda (inclusive o STATUS) e o nome da pessoa
        c.execute("""
            SELECT agenda.*, pessoas.nome,
            strftime('%d/%m/%Y', agenda.data) AS data_recebeu,
            strftime('%d/%m/%Y', date(agenda.data, '+1 day')) AS data_entrega
            FROM agenda 
            JOIN pessoas ON pessoas.id = agenda.pessoa_id 
            ORDER BY agenda.data
        """)
        dados = c.fetchall()
        # -----------------------------------------------

        # Verifica se o usuário logado tem uma visita futura ou hoje
        if session.get('user_id'):
            c.execute("""
                SELECT data, status FROM agenda 
                WHERE pessoa_id = ? AND data >= ? 
                ORDER BY data ASC LIMIT 1
            """, (session['user_id'], hoje_str))
            res = c.fetchone()
            
            if res:
                proxima_data_obj = datetime.strptime(res['data'], "%Y-%m-%d").date()
                dias_faltando = (proxima_data_obj - hoje_dt).days
                # Aqui pegamos o status (pendente ou recebido) para o painel principal
                status_hoje = res['status']

    return render_template("agenda.html", 
                           agenda=dados, 
                           hoje=hoje_str, 
                           dias_faltando=dias_faltando, 
                           proxima_data=proxima_data_obj, 
                           status_hoje=status_hoje)

# --- CONFIRMAR QUE RECEBEU A CAPELA ---
@app.route("/confirmar_recebimento", methods=["POST"])
def confirmar_recebimento():
    if not session.get('user_id'): return redirect(url_for("login"))
    hoje_str = date.today().strftime("%Y-%m-%d")
    
    with get_db() as db:
        c = db.cursor()
        # Atualiza apenas o status para 'recebido'
        c.execute("UPDATE agenda SET status = 'recebido' WHERE pessoa_id = ? AND data = ?", 
                  (session['user_id'], hoje_str))
        db.commit()
    flash("Confirmado! A Capela está com você hoje. ✝️", "success")
    return redirect(url_for("agenda"))

# --- ENTREGAR / ATRASAR ---
@app.route("/atrasar", methods=["POST"])
def atrasar():
    user_id = session.get('user_id')
    user_role = session.get('role')
    if not user_id: return redirect(url_for("login"))
    
    dias = int(request.form.get("dias", 1))
    data_clicada = request.form.get("data_clicada")
    
    with get_db() as db:
        c = db.cursor()
        
        # Verifica se o usuário tem permissão sobre essa data
        c.execute("SELECT pessoa_id FROM agenda WHERE data = ?", (data_clicada,))
        reg = c.fetchone()
        
        if reg and (reg['pessoa_id'] == user_id or user_role == 'admin'):
            # ATUALIZA A DATA E RESET_STATUS: Isso faz a Laura (próxima) ver o botão de receber
            c.execute("""
                UPDATE agenda 
                SET data = date(data, '+' || ? || ' day'), status = 'pendente' 
                WHERE data >= ?
            """, (dias, data_clicada))
            db.commit()
            flash("Entrega registrada! A escala andou para o próximo.", "success")
        else:
            flash("Você não tem permissão para alterar esta data.", "danger")
                
    return redirect(url_for("agenda"))

# --- LOGIN E LOGOUT ---
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
                session['user_id'] = user['id']
                session['nome'] = user['nome']
                session['role'] = user['role']
                
                # SE FOR O PRIMEIRO LOGIN, MANDA PARA A TELA DE TROCAR SENHA
                if user['primeiro_login'] == 1:
                    flash("Este é seu primeiro acesso. Por favor, crie uma senha segura.", "info")
                    return redirect(url_for("trocar_senha"))
                
                return redirect(url_for("agenda"))
        flash("Login ou senha incorretos.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/trocar_senha", methods=["GET", "POST"])
def trocar_senha():
    if not session.get('user_id'): return redirect(url_for("login"))
    
    if request.method == "POST":
        nova_senha = request.form.get("nova_senha")
        confirmacao = request.form.get("confirmacao")
        
        if nova_senha != confirmacao:
            flash("As senhas não coincidem!", "danger")
            return redirect(url_for("trocar_senha"))
            
        with get_db() as db:
            c = db.cursor()
            # Atualiza a senha e marca que o primeiro login foi concluído (0)
            c.execute("UPDATE pessoas SET senha = ?, primeiro_login = 0 WHERE id = ?", 
                      (nova_senha, session['user_id']))
            db.commit()
            
        flash("Senha atualizada com sucesso!", "success")
        return redirect(url_for("agenda"))
        
    return render_template("trocar_senha.html")

# --- ADMIN: GERENCIAR PESSOAS ---
@app.route("/pessoas")
def pessoas():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT * FROM pessoas ORDER BY ordem")
        lista = c.fetchall()
    return render_template("pessoas.html", pessoas=lista)

# --- ADMIN: GERAR AGENDA INICIAL ---
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
                c.execute("INSERT INTO agenda (data, pessoa_id, status) VALUES (?, ?, 'pendente')", 
                          (data_corrida.strftime("%Y-%m-%d"), lista[i % len(lista)]))
                data_corrida += timedelta(days=1)
            db.commit()
    flash("Agenda gerada para os próximos 90 dias!", "success")
    return redirect(url_for("agenda"))

# ROTA PARA EXIBIR A PÁGINA DE CADASTRO
@app.route("/cadastrar")
def cadastrar_page():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    return render_template("cadastrar.html")

# ROTA PARA SALVAR O NOVO MEMBRO NO BANCO
@app.route("/add_pessoa", methods=["POST"])
def add_pessoa():
    if session.get('role') != 'admin': return redirect(url_for("login"))
    
    nome = request.form.get("nome")
    login = request.form.get("login").strip().lower()
    senha = request.form.get("senha")
    ordem = request.form.get("ordem")
    
    with get_db() as db:
        c = db.cursor()
        try:
            c.execute("""
                INSERT INTO pessoas (nome, login, senha, role, ordem, ativo, primeiro_login) 
                VALUES (?, ?, ?, 'user', ?, 1, 1)
            """, (nome, login, senha, ordem))
            db.commit()
            flash(f"{nome} cadastrado com sucesso!", "success")
        except Exception as e:
            flash("Erro: Este login já existe ou os dados são inválidos.", "danger")
            
    return redirect(url_for("pessoas"))

# --- REMOVER PESSOA ---
@app.route("/remover_pessoa/<int:id>")
def remover_pessoa(id):
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("DELETE FROM pessoas WHERE id = ?", (id,))
        c.execute("DELETE FROM agenda WHERE pessoa_id = ?", (id,)) # Limpa a agenda dele também
        db.commit()
    flash("Membro removido com sucesso.", "success")
    return redirect(url_for("pessoas"))

# --- MOVER PESSOA (SUBIR/DESCER NA ORDEM) ---
@app.route("/mover_pessoa/<int:id>/<direcao>")
def mover_pessoa(id, direcao):
    if session.get('role') != 'admin': return redirect(url_for("login"))
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT ordem FROM pessoas WHERE id = ?", (id,))
        ordem_atual = c.fetchone()['ordem']
        
        nova_ordem = ordem_atual - 1 if direcao == "subir" else ordem_atual + 1
        
        # Troca a ordem com quem estava na posição de destino
        c.execute("UPDATE pessoas SET ordem = ? WHERE ordem = ?", (ordem_atual, nova_ordem))
        c.execute("UPDATE pessoas SET ordem = ? WHERE id = ?", (nova_ordem, id))
        db.commit()
    return redirect(url_for("pessoas"))

# --- EDITAR PESSOA ---
@app.route("/editar_pessoa/<int:id>", methods=["GET", "POST"])
def editar_pessoa(id):
    if session.get('role') != 'admin': 
        return redirect(url_for("login"))
    
    with get_db() as db:
        c = db.cursor()
        if request.method == "POST":
            nome = request.form.get("nome")
            login = request.form.get("login").strip().lower()
            senha = request.form.get("senha")
            ordem = request.form.get("ordem")
            role = request.form.get("role")  # <-- Esta linha captura o valor do HTML
            
            # O SQL precisa incluir o campo 'role'
            c.execute("""
                UPDATE pessoas 
                SET nome=?, login=?, senha=?, ordem=?, role=? 
                WHERE id=?
            """, (nome, login, senha, ordem, role, id))
            db.commit()
            flash("Perfil atualizado com sucesso!", "success")
            return redirect(url_for("pessoas"))
        
        c.execute("SELECT * FROM pessoas WHERE id = ?", (id,))
        res = c.fetchone()
    return render_template("cadastrar.html", pessoa=res)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)