from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
import smtplib
smtplib.SMTP("smtp.gmail.com", 587)
from flask_mail import Mail, Message
import pandas as pd  # ajouté pour Excel




app = Flask(__name__)

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='garbamohamedseidoul@gmail.com',
    MAIL_PASSWORD='auzkkrwvwiqlppdh', 
)


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
    
conn1 = get_db_connection("port_drh")
conn2 = get_db_connection("port_dsi")
conn3 = get_db_connection("port_dtl")

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

import mysql.connector

def get_all_databases_with_bases():
    valid_dbs = []  # initialiser la liste avant tout
    try:
        # connexion générale
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = [db[0] for db in cursor.fetchall()]

        for db_name in dbs:
            # Ignorer les bases systèmes
            if db_name in ["information_schema", "mysql", "performance_schema", "phpmyadmin"]:
                continue

            conn_db = None
            try:
                # connexion à la base spécifique
                conn_db = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",
                    database=db_name
                )
                cursor_db = conn_db.cursor()
                cursor_db.execute("SHOW TABLES")  # récupérer toutes les tables
                tables = cursor_db.fetchall()

                if tables:  # si la base contient au moins une table
                    valid_dbs.append(db_name)

            except mysql.connector.Error:
                continue  # ignore les bases où la connexion échoue
            finally:
                if conn_db:
                    conn_db.close()  # ferme seulement si la connexion a été créée

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
    base1 = data.get("base1", "base1")
    base2 = data.get("base2", "base2")
    try:
        # 1️⃣ Créer le DataFrame pour Excel
        df = pd.DataFrame(differences)
        #Ce code pour remplacer les bases par
        df.columns = [
    col.replace("base1_", f"{base1}_")
       .replace("base2_", f"{base2}_")
    for col in df.columns
]

        # Nom du fichier Excel temporaire
        excel_file = "notification.xlsx"
        df.to_excel(excel_file, index=False)

        # 2️⃣ Préparer le mail
        msg = Message(
            subject="Notification des différences",
            sender=app.config['MAIL_USERNAME'],
            recipients=["garbamohamedseidoul@gmail.com"],   # tu peux ajouter d'autres emails ici
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

    conn_global = mysql.connector.connect(
        host="localhost",
        user="root",
        password=""
    )

    cursor_global = conn_global.cursor()
    cursor_global.execute("SHOW DATABASES")

    ignore = {
        "mysql",
        "information_schema",
        "performance_schema",
        "phpmyadmin",
        "test"
    }

    all_databases = [
        db[0] for db in cursor_global.fetchall()
        if db[0] not in ignore
    ]

    conn_global.close()

    # 🔥 parcourir chaque base
    for db_name in all_databases:

        conn = get_db_connection(db_name)
        if not conn:
            continue

        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW TABLES")
        tables = [list(t.values())[0] for t in cursor.fetchall()]

        for table in tables:

            if table == "bases":
                continue

            try:
                # 🔥 ON PREND SEULEMENT id
                cursor.execute(f"SELECT id FROM `{table}`")

                rows = cursor.fetchall()

                for r in rows:

                    bases_a_traiter.append({
                        "nom_base": db_name,
                        "table": table,
                        "id": r.get("id", "")
                    })

            except:
                pass

        conn.close()

    return render_template(
        "index.html",
        bases_a_traiter=bases_a_traiter,
        all_databases=all_databases
    )


@app.route("/comparaison", methods=["GET", "POST"])
def comparaison():
    notification = ""
    tables_differences = {}
    bases_disponibles = get_all_databases_with_bases()
    all_tables = []

    # récupérer les bases choisies dans le formulaire
    base1_name = request.form.get("base1")
    base2_name = request.form.get("base2")

    # si les deux bases sont sélectionnées, récupérer leurs tables
    tables1 = []
    tables2 = []

    if base1_name:
        conn1 = get_db_connection(base1_name)
        if conn1:
            cursor1 = conn1.cursor(dictionary=True)
            cursor1.execute("SHOW TABLES")
            tables1 = [list(t.values())[0] for t in cursor1.fetchall()]
            conn1.close()

    if base2_name:
        conn2 = get_db_connection(base2_name)
        if conn2:
            cursor2 = conn2.cursor(dictionary=True)
            cursor2.execute("SHOW TABLES")
            tables2 = [list(t.values())[0] for t in cursor2.fetchall()]
            conn2.close()

    # On accepte seulement les bases qui ont au moins 1 table
    if tables1 or tables2:
        all_tables = sorted(set(tables1) | set(tables2))

    # si on clique sur Comparer
    if request.method == "POST" :
        base1_name and base2_name
        selected_tables = request.form.getlist("tables")

        if not selected_tables:
            flash("⚠️ Veuillez choisir au moins une table à comparer !", "warning")
        else:
            # comparer uniquement les tables cochées
            conn1 = get_db_connection(base1_name)
            conn2 = get_db_connection(base2_name)
            cursor1 = conn1.cursor(dictionary=True)
            cursor2 = conn2.cursor(dictionary=True)

            for table in selected_tables:
                table1_exists = table in tables1
                table2_exists = table in tables2

                if not table1_exists or not table2_exists:
                    tables_differences.setdefault(table, []).append({
                        "table": table,
                        "base1_table": "✅ existe" if table1_exists else "❌ absente",
                        "base2_table": "✅ existe" if table2_exists else "❌ absente"
                    })
                    continue

                cursor1.execute(f"SHOW COLUMNS FROM `{table}`")
                cols1 = [c["Field"] for c in cursor1.fetchall()]

                cursor2.execute(f"SHOW COLUMNS FROM `{table}`")
                cols2 = [c["Field"] for c in cursor2.fetchall()]

                common_cols = list(set(cols1) & set(cols2))
                if not common_cols:
                    continue

                cursor1.execute(f"SELECT * FROM `{table}`")
                rows1 = cursor1.fetchall()

                cursor2.execute(f"SELECT * FROM `{table}`")
                rows2 = cursor2.fetchall()

                key = next((k for k in ["id", "identifiant"] if k in common_cols), common_cols[0])
                dict1 = {r[key]: r for r in rows1 if key in r}
                dict2 = {r[key]: r for r in rows2 if key in r}

                all_ids = set(dict1.keys()) | set(dict2.keys())

                for ident in all_ids:
                    r1 = dict1.get(ident)
                    r2 = dict2.get(ident)

                    row_diff = {}
                    has_diff = False
                    for col in common_cols:
                        val1 = r1.get(col) if r1 else None
                        val2 = r2.get(col) if r2 else None
                        if val1 != val2:
                            has_diff = True
                        row_diff[f"base1_{col}"] = val1 if val1 is not None else "❌ absent"
                        row_diff[f"base2_{col}"] = val2 if val2 is not None else "❌ absent"
                    if has_diff or not r1 or not r2:
                        row_diff["table"] = table
                        row_diff[key] = ident
                        tables_differences.setdefault(table, []).append(row_diff)

            notification = (
                f"⚠️ {sum(len(v) for v in tables_differences.values())} différence(s)"
                if tables_differences else "✅ aucune différence"
            )
            conn1.close()
            conn2.close()

    return render_template(
        "comparaison.html",
        bases=bases_disponibles,
        all_tables=all_tables,
        tables_differences=tables_differences,
        notification=notification
    )



@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    # Récupère dynamiquement toutes les bases pour le formulaire
    bases_disponibles = get_all_databases_with_bases()

    if request.method == "POST":
        # Choix base existante ou nouvelle base
        nom_base_select = request.form.get("nom_base_select")
        nom_base_new = request.form.get("nom_base_new")

        # Déterminer le nom de la base à utiliser
        if nom_base_new:
            nom_base = nom_base_new
        elif nom_base_select:
            nom_base = nom_base_select
        else:
            flash("Veuillez choisir ou créer une base !", "danger")
            return redirect(url_for("ajouter"))

        nom_table = request.form.get("nom_table")
        identifiant = request.form.get("identifiant")
        nom = request.form.get("nom")
        age = request.form.get("age")
        infos = request.form.get("infos", "")



        # Créer la base si elle n'existe pas
        conn = get_or_create_db(nom_base)
        if not conn:
            flash(f"Erreur : impossible de se connecter ou créer la base '{nom_base}' !", "danger")
            return redirect(url_for("ajouter"))

        cursor = conn.cursor(dictionary=True)




        # Vérifier si la table personnalisée existe déjà
        cursor.execute(f"SHOW TABLES LIKE %s", (nom_table,))
        if not cursor.fetchone():
            # Créer la table personnalisée
            cursor.execute(f"""
                CREATE TABLE {nom_table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    identifiant INT,
                    nom VARCHAR(100),
                    age INT,
                    infos TEXT
                )
            """)
            conn.commit()

        # Ajouter la ligne dans la table 'bases'
        cursor.execute(
    f"INSERT INTO `{nom_table}` (identifiant, nom, age, infos) VALUES (%s, %s, %s, %s)",
    (identifiant, nom, age, infos)
)
        conn.commit()
        conn.close()

        flash(f"✅ Base '{nom_base}' et table '{nom_table}' créées avec succès !", "success")
        return redirect(url_for("index"))

    return render_template("ajouter.html", bases=bases_disponibles)


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