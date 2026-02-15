from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
from flask_mail import Mail, Message
import pandas as pd  # ajouté pour Excel



app = Flask(__name__)

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='garbamohamedseidoul@gmail.com',
    MAIL_PASSWORD='cvwizdbmhblhznru',
)
DATABASE = r"C:\Users\GARBA\Desktop\port_autonome1\database.db"

mail = Mail(app)
app.secret_key = "secret123"

def get_db_connection(database_name):
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database=database_name
        )
    except mysql.connector.Error as err:
        print("Erreur MySQL :", err)
        return None
    
conn1 = get_db_connection("port_autonome1")
conn2 = get_db_connection("port_autonome2")

if not conn1 or not conn2:
    print("Erreur de connexion au bases")


def get_or_create_db(database_name):
    try:
        # Connexion au serveur MySQL (sans database)
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
        conn.close()

        # Connexion à la base
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database=database_name
        )
    except mysql.connector.Error as err:
        print("Erreur MySQL :", err)
        return None

def get_all_databases_with_bases():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = [db[0] for db in cursor.fetchall()]
        valid_dbs = []

        for db_name in dbs:
            # Se connecter à la base
            try:
                conn_db = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",
                    database=db_name
                )
                cursor_db = conn_db.cursor()
                cursor_db.execute("SHOW TABLES LIKE 'bases'")
                if cursor_db.fetchone():  # si la table 'bases' existe
                    valid_dbs.append(db_name)
                conn_db.close()
            except:
                continue
        conn.close()
        return valid_dbs
    except mysql.connector.Error as e:
        print("Erreur MySQL :", e)
        return []




def init_db():
    conn = get_db_connection()
    if not conn:
        print("Erreur de connexion à MySQL")
        return

    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS base (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom_base VARCHAR(100),
            valeur1 INT,
            valeur2 INT,
            valeur3 INT,
            valeur4 INT,
            statut ENUM('a_traiter','traite') DEFAULT 'a_traiter',
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultats_comparaison (
            id INT AUTO_INCREMENT PRIMARY KEY,
            base1 VARCHAR(100),
            base2 VARCHAR(100),
            difference TEXT,
            date_comparaison TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donnees (
            id INT,
            nom VARCHAR(100),
            valeur INT,
            nom_base VARCHAR(100)
        )
    ''')

    conn.commit()
    conn.close()


# -------------------- ROUTE POUR NOTIFIER AVEC EXCEL --------------------
@app.route('/notifier', methods=['POST'])
def notifier():
    data = request.get_json()
    differences = data.get("differences", [])

    if not differences:
        return jsonify({"status": "error", "message": "Aucune différence à notifier"}), 400

    try:
        # 1️⃣ Créer le DataFrame pour Excel
        df = pd.DataFrame(differences)

        # Nom du fichier Excel temporaire
        excel_file = "notification.xlsx"
        df.to_excel(excel_file, index=False)

        # 2️⃣ Préparer le mail
        msg = Message(
            subject="Notification des différences",
            sender=app.config['MAIL_USERNAME'],
            recipients=["garbamohamedseidoul@gmail.com"],  # tu peux ajouter d'autres emails ici
            body="Bonjour,\n\nVeuillez trouver ci-joint le tableau des différences détectées.\n\nCordialement."
        )

        # 3️⃣ Attacher le fichier Excel
        with open(excel_file, "rb") as f:
            msg.attach(
                "notification.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f.read()
            )

        # 4️⃣ Envoyer le mail
        mail.send(msg)
        print("✅ MAIL ENVOYÉ AVEC EXCEL")

        return jsonify({"status": "success", "message": f"{len(differences)} différences envoyées avec succès"})

    except Exception as e:
        print("❌ ERREUR MAIL :", e)
        return jsonify({"status": "error", "message": str(e)}), 500

# -------------------- ROUTES EXISTANTES --------------------
@app.route("/")
def index():
    bases_a_traiter = []

    # 1️⃣ Récupère dynamiquement toutes les bases avec la table 'bases'
    all_dbs = get_all_databases_with_bases()  # ta fonction déjà présente

    for db_name in all_dbs:
        conn = get_db_connection(db_name)
        if not conn:
            continue
        cursor = conn.cursor(dictionary=True)

        # Récupère seulement identifiant, nom, age et nom_base
        cursor.execute("""
            SELECT identifiant, nom, age, nom_base 
            FROM bases 
            WHERE statut = 'a_traiter'
        """)
        rows = cursor.fetchall()
        bases_a_traiter += rows
        conn.close()

    return render_template("index.html", bases_a_traiter=bases_a_traiter)


@app.route("/comparaison", methods=["GET", "POST"])
def comparaison():
    differences_par_table = {}
    notification = ""

    bases_disponibles = get_all_databases_with_bases()

    if request.method == "POST":
        base1_name = request.form.get("base1")
        base2_name = request.form.get("base2")

        conn1 = get_db_connection(base1_name)
        conn2 = get_db_connection(base2_name)

        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()

        # Récupérer toutes les tables
        cursor1.execute("SHOW TABLES")
        tables_base1 = [t[0] for t in cursor1.fetchall()]

        cursor2.execute("SHOW TABLES")
        tables_base2 = [t[0] for t in cursor2.fetchall()]

        # Tables à comparer : union des deux
        all_tables = list(set(tables_base1 + tables_base2))

        for table in all_tables:
            # Récupérer toutes les lignes de la table
            rows1 = []
            rows2 = []
            champs = []

            if table in tables_base1:
                cursor1.execute(f"SELECT * FROM {table}")
                rows1 = [dict(zip([desc[0] for desc in cursor1.description], r)) for r in cursor1.fetchall()]
                champs = [desc[0] for desc in cursor1.description]

            if table in tables_base2:
                cursor2.execute(f"SELECT * FROM {table}")
                rows2 = [dict(zip([desc[0] for desc in cursor2.description], r)) for r in cursor2.fetchall()]
                if not champs:  # si table existe seulement dans base2
                    champs = [desc[0] for desc in cursor2.description]

            diffs_table = []

            max_len = max(len(rows1), len(rows2))
            for i in range(max_len):
                row1 = rows1[i] if i < len(rows1) else {c: "—" for c in champs}
                row2 = rows2[i] if i < len(rows2) else {c: "—" for c in champs}

                row_diff_base1 = []
                row_diff_base2 = []

                for c in champs:
                    v1 = row1.get(c, "—")
                    v2 = row2.get(c, "—")
                    if v1 != v2:
                        row_diff_base1.append(f"{c}: {v1}")
                        row_diff_base2.append(f"{c}: {v2}")

                if row_diff_base1 or row_diff_base2:
                    diffs_table.append({
                        "ligne": i+1,
                        "base1": ", ".join(row_diff_base1),
                        "base2": ", ".join(row_diff_base2)
                    })

            differences_par_table[table] = diffs_table

        conn1.close()
        conn2.close()
        notification = "Comparaison terminée"

    return render_template("comparaison.html",
                           differences_par_table=differences_par_table,
                           notification=notification,
                           bases=bases_disponibles)





@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    if request.method == "POST":
        nom_base = request.form["nom_base"]
        identifiant = int(request.form["identifiant"])
        nom = request.form["nom"]
        age = int(request.form["age"])
        infos = request.form["infos"]

        # Connexion à la base (la crée si elle n'existe pas)
        conn = get_or_create_db(nom_base)
        if not conn:
            flash(f"Erreur : impossible de créer ou se connecter à la base {nom_base} !", "danger")
            return redirect(url_for("ajouter"))

        cursor = conn.cursor(dictionary=True)

        # Créer la table 'bases' si elle n'existe pas
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS bases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom_base VARCHAR(100),
                identifiant INT,
                nom VARCHAR(100),
                age INT,
                infos TEXT,
                statut ENUM('a_traiter','traite') DEFAULT 'a_traiter'
            )
        """)
        conn.commit()

        # Insérer la ligne
        cursor.execute(
            "INSERT INTO bases (nom_base, identifiant, nom, age, infos, statut) VALUES (%s,%s,%s,%s,%s,%s)",
            (nom_base, identifiant, nom, age, infos, 'a_traiter')
        )
        conn.commit()
        conn.close()

        flash(f"Ligne ajoutée dans la base {nom_base} avec succès !", "success")
        return redirect(url_for("index"))

    return render_template("ajouter.html")




@app.route("/liste")
def liste():
    conn = get_db_connection()
    if not conn:
        return "Erreur de connexion à MySQL", 500

    cursor = conn.cursor(dictionary=True)  # Permet d’accéder aux colonnes par nom
    cursor.execute("SELECT * FROM bases ORDER BY id DESC")
    bases = cursor.fetchall()
    conn.close()
    return render_template("liste.html", bases=bases)


# -------------------- LANCEMENT DE L'APP --------------------
if __name__ == "__main__":
    
    app.run(debug=True)