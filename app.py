
from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db():
    return sqlite3.connect("capela.db")

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pessoas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        ordem INTEGER NOT NULL,
        ativo INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data DATE,
        pessoa_id INTEGER,
        FOREIGN KEY(pessoa_id) REFERENCES pessoas(id)
    )
    """)

    db.commit()
    db.close()

@app.route("/")
def agenda():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
    SELECT agenda.data, pessoas.nome
    FROM agenda
    JOIN pessoas ON pessoas.id = agenda.pessoa_id
    ORDER BY agenda.data
    """)
    dados = cursor.fetchall()
    return render_template("agenda.html", agenda=dados)

@app.route("/pessoas")
def pessoas():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM pessoas ORDER BY ordem")
    dados = cursor.fetchall()
    return render_template("pessoas.html", pessoas=dados)

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        nome = request.form["nome"]
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM pessoas")
        ordem = cursor.fetchone()[0]
        cursor.execute("INSERT INTO pessoas (nome, ordem) VALUES (?,?)", (nome, ordem))
        db.commit()
        return redirect("/pessoas")
    return render_template("cadastrar.html")

@app.route("/gerar_agenda")
def gerar_agenda():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM agenda")
    cursor.execute("SELECT id FROM pessoas WHERE ativo=1 ORDER BY ordem")
    pessoas = cursor.fetchall()
    data = datetime.today()
    for pessoa in pessoas:
        cursor.execute(
            "INSERT INTO agenda (data, pessoa_id) VALUES (?,?)",
            (data.strftime("%Y-%m-%d"), pessoa[0])
        )
        data += timedelta(days=1)
    db.commit()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
