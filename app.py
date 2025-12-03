from flask import Flask, render_template, request, redirect, url_for, send_file, abort
import sqlite3
import os
import io
from datetime import datetime

app = Flask(__name__)

DB_PATH = "database.db"

CATEGORIES = {
    "poemas": {
        "name": "Poemas",
        "icon": "📝",
        "description": "Rimas, versos y sentimientos en palabras."
    },
    "cuentos": {
        "name": "Cuentos",
        "icon": "📖",
        "description": "Historias, aventuras y personajes increíbles."
    },
    "escritos": {
        "name": "Escritos",
        "icon": "💡",
        "description": "Ideas, notas, pensamientos y todo lo demás."
    },
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE writings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()


@app.route("/")
def welcome():
    # Pantalla de bienvenida "Bienvenido al mundo de Ryan"
    return render_template("welcome.html")


@app.route("/inicio")
def home():
    # Pantalla con las 3 categorías: Poemas, Cuentos, Escritos
    return render_template("home.html")


@app.route("/categoria/<slug>", methods=["GET", "POST"])
def category_view(slug):
    if slug not in CATEGORIES:
        abort(404)

    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        writing_id = request.form.get("id")
        title = request.form.get("title", "").strip() or "Sin título"
        # Contenido viene desde Quill (HTML)
        content = request.form.get("content", "").strip()
        now = datetime.now().isoformat(timespec="seconds")

        if writing_id:
            # Actualizar
            cur.execute(
                """
                UPDATE writings
                SET title = ?, content = ?, updated_at = ?
                WHERE id = ? AND category = ?
                """,
                (title, content, now, writing_id, slug),
            )
        else:
            # Crear nuevo
            cur.execute(
                """
                INSERT INTO writings (category, title, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (slug, title, content, now, now),
            )

        conn.commit()
        conn.close()
        return redirect(url_for("category_view", slug=slug))

    # GET: mostrar lista + texto en edición (si aplica)
    edit_id = request.args.get("edit_id")
    editing = None

    if edit_id:
        cur.execute(
            "SELECT * FROM writings WHERE id = ? AND category = ?",
            (edit_id, slug),
        )
        editing = cur.fetchone()

    cur.execute(
        "SELECT * FROM writings WHERE category = ? ORDER BY updated_at DESC",
        (slug,),
    )
    writings = cur.fetchall()
    conn.close()

    return render_template(
        "category.html",
        slug=slug,
        config=CATEGORIES[slug],
        writings=writings,
        editing=editing,
    )


@app.route("/texto/<int:writing_id>/descargar")
def download_text(writing_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM writings WHERE id = ?", (writing_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        abort(404)

    title = row["title"] or "sin_titulo"
    # Guardamos el HTML tal cual
    content = row["content"] or ""

    safe_title = (
        title.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    # Descargar como archivo .html para conservar formato
    file_stream = io.BytesIO(content.encode("utf-8"))
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=f"{safe_title}.html",
        mimetype="text/html; charset=utf-8",
    )


@app.route("/texto/<int:writing_id>/borrar", methods=["POST"])
def delete_text(writing_id):
    slug = request.form.get("slug")
    if slug not in CATEGORIES:
        abort(400)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM writings WHERE id = ? AND category = ?", (writing_id, slug))
    conn.commit()
    conn.close()
    return redirect(url_for("category_view", slug=slug))


if __name__ == "__main__":
    init_db()
    # Para desarrollo en tu máquina:
    app.run(debug=True, port=5020)
