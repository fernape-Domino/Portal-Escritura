from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    abort,
    session,
)
import sqlite3
import os
import io
from datetime import datetime
import re
import textwrap

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

# Clave para manejar la sesión (PIN)
app.config["SECRET_KEY"] = "cambia-esta-clave-por-una-mas-larga"

# PIN para entrar al mundo de Ryan
PIN_CODE = "1234"  # <- cámbialo aquí por el que tú quieras

DB_PATH = "database.db"

CATEGORIES = {
    "poemas": {
        "name": "Poemas",
        "icon": "📝",
        "description": "Rimas, versos y sentimientos en palabras.",
    },
    "cuentos": {
        "name": "Cuentos",
        "icon": "📖",
        "description": "Historias, aventuras y personajes increíbles.",
    },
    "escritos": {
        "name": "Escritos",
        "icon": "💡",
        "description": "Ideas, notas, pensamientos y todo lo demás.",
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


# ----- Decorador para proteger rutas con PIN ----- #
from functools import wraps


def pin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authorized"):
            return redirect(url_for("pin"))
        return f(*args, **kwargs)

    return wrapper


# ----- Rutas ----- #


@app.route("/")
def welcome():
    # Pantalla de bienvenida "Bienvenido al mundo de Ryan"
    return render_template("welcome.html")


@app.route("/pin", methods=["GET", "POST"])
def pin():
    error = None
    if request.method == "POST":
        entered = request.form.get("pin", "")
        if entered == PIN_CODE:
            session["authorized"] = True
            return redirect(url_for("home"))
        else:
            error = "PIN incorrecto. Inténtalo de nuevo."
    return render_template("pin.html", error=error)


@app.route("/inicio")
@pin_required
def home():
    # Pantalla con las 3 categorías: Poemas, Cuentos, Escritos
    return render_template("home.html")


@app.route("/categoria/<slug>", methods=["GET", "POST"])
@pin_required
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
            cur.execute(
                """
                UPDATE writings
                SET title = ?, content = ?, updated_at = ?
                WHERE id = ? AND category = ?
                """,
                (title, content, now, writing_id, slug),
            )
        else:
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
@pin_required
def download_text(writing_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM writings WHERE id = ?", (writing_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        abort(404)

    title = row["title"] or "sin_titulo"
    html_content = row["content"] or ""

    # Convertir HTML a texto simple para el PDF (quitamos etiquetas)
    text_content = re.sub("<[^<]+?>", "", html_content)
    safe_title = (
        title.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    # Crear PDF en memoria
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Título en el PDF
    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, title)
    y -= 30

    # Cuerpo del texto
    p.setFont("Helvetica", 11)

    # Hacemos wrap para que no se salga de la página
    wrapped_lines = []
    for line in text_content.splitlines():
        wrapped_lines.extend(textwrap.wrap(line, width=90) or [""])

    for line in wrapped_lines:
        if y < 50:  # salto de página
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - 50
        p.drawString(50, y, line)
        y -= 14

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{safe_title}.pdf",
        mimetype="application/pdf",
    )


@app.route("/texto/<int:writing_id>/borrar", methods=["POST"])
@pin_required
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
    app.run(debug=True, port=5020)
