from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta, date

app = Flask(__name__)
DB_NAME = "capela.db"

# ---------- DB ----------
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
            ordem INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL,
            pessoa_id INTEGER NOT NULL,
            FOREIGN KEY(pessoa_id) REFERENCES pessoas(id)
        )
        """)

# ---------- ROTAS ----------
@app.route("/")
def agenda():
    hoje = date.today().strftime("%Y-%m-%d")

    with get_db() as db:
        c = db.cursor()
        c.execute("""
            SELECT 
                agenda.id,
                agenda.data,
                strftime('%d-%m-%Y', agenda.data) AS data_br,
                pessoas.nome
            FROM agenda
            JOIN pessoas ON pessoas.id = agenda.pessoa_id
            ORDER BY agenda.data
        """)
        dados = c.fetchall()

    return render_template("agenda.html", agenda=dados, hoje=hoje)

@app.route("/pessoas")
def pessoas():
    with get_db() as db:
        c = db.cursor()
        c.execute("SELECT * FROM pessoas ORDER BY ordem")
        pessoas = c.fetchall()
    return render_template("pessoas.html", pessoas=pessoas)

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        nome = request.form["nome"]

        with get_db() as db:
            c = db.cursor()
            c.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM pessoas")
            ordem = c.fetchone()[0]
            c.execute(
                "INSERT INTO pessoas (nome, ordem) VALUES (?, ?)",
                (nome, ordem)
            )

        return redirect("/pessoas")

    return render_template("cadastrar.html")

@app.route("/gerar")
def gerar_agenda():
    with get_db() as db:
        c = db.cursor()

        c.execute("DELETE FROM agenda")

        c.execute("SELECT id FROM pessoas WHERE ativo = 1 ORDER BY ordem")
        pessoas = [p["id"] for p in c.fetchall()]

        if not pessoas:
            return redirect("/")

        data = date.today()
        dias = 90
        i = 0

        for _ in range(dias):
            pessoa_id = pessoas[i % len(pessoas)]
            c.execute(
                "INSERT INTO agenda (data, pessoa_id) VALUES (?, ?)",
                (data.strftime("%Y-%m-%d"), pessoa_id)
            )
            data += timedelta(days=1)
            i += 1

    return redirect("/")

@app.route("/atrasar", methods=["POST"])
def atrasar():
    dias = int(request.form["dias"])
    hoje = date.today().strftime("%Y-%m-%d")

    with get_db() as db:
        c = db.cursor()
        c.execute("""
            UPDATE agenda
            SET data = date(data, '+' || ? || ' day')
            WHERE data >= ?
        """, (dias, hoje))

    return redirect("/")

# ---------- START ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
