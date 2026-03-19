
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
import smtplib
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


#  ROUTE POUR NOTIFIER AVEC EXCEL 
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

#  ROUTES EXISTANTES 
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
        "phpmyadmin"
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

    # Table 1 = différences intra-base
    diff_base1 = {}
    diff_base2 = {}

    # Table 2 = identiques intra-base
    lignes_identiques_base1 = {}
    lignes_identiques_base2 = {}

    selected_tables_base1 = []
    selected_tables_base2 = []

    bases_disponibles = get_all_databases_with_bases()

    base1_name = request.form.get("base1")
    base2_name = request.form.get("base2")

    tables1, tables2 = [], []

    # =============================
    # PHASE 1 : Récupération des tables
    # =============================
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

    # =============================
    # PHASE 2 : Traitement POST
    # =============================
    if request.method == "POST":

        # Vérification minimale
        if not base1_name or not base2_name:
            notification = "Veuillez sélectionner deux bases."
        else:

            # ==========================================================
            # PHASE 3 : COMPARAISON INTRA-BASE 1 (expo vs users)
            # ==========================================================
            if "expo" in tables1 and "users" in tables1:

                conn = get_db_connection(base1_name)
                cursor = conn.cursor(dictionary=True)

                cursor.execute("SELECT * FROM expo")
                expo_rows = cursor.fetchall()

                cursor.execute("SELECT * FROM users")
                users_rows = cursor.fetchall()

                conn.close()

                expo_dict = {r["id"]: r for r in expo_rows}
                users_dict = {r["id"]: r for r in users_rows}

                table1_diff = []   # différences
                table2_same = []   # identiques

                all_ids = set(expo_dict.keys()) | set(users_dict.keys())

                for rid in all_ids:
                    r1 = expo_dict.get(rid, {})
                    r2 = users_dict.get(rid, {})

                    row = {"id": rid}
                    has_diff = False

                    for col in ["Num_Facture", "Libelle"]:
                        v1 = str(r1.get(col, ""))
                        v2 = str(r2.get(col, ""))

                        row[f"{col}_expo"] = v1
                        row[f"{col}_users"] = v2

                        if v1 != v2:
                            has_diff = True

                    if has_diff:
                        table1_diff.append(row)   # Table 1
                    else:
                        table2_same.append(row)   # Table 2

                diff_base1["expo vs users"] = table1_diff
                lignes_identiques_base1["expo vs users"] = table2_same

            # ==========================================================
            # PHASE 4 : COMPARAISON INTRA-BASE 2 (expo vs users)
            # ==========================================================
            if "expo" in tables2 and "users" in tables2:

                conn = get_db_connection(base2_name)
                cursor = conn.cursor(dictionary=True)

                cursor.execute("SELECT * FROM expo")
                expo_rows = cursor.fetchall()

                cursor.execute("SELECT * FROM users")
                users_rows = cursor.fetchall()

                conn.close()

                expo_dict = {r["id"]: r for r in expo_rows}
                users_dict = {r["id"]: r for r in users_rows}

                table1_diff = []
                table2_same = []

                all_ids = set(expo_dict.keys()) | set(users_dict.keys())

                for rid in all_ids:
                    r1 = expo_dict.get(rid, {})
                    r2 = users_dict.get(rid, {})

                    row = {"id": rid}
                    has_diff = False

                    for col in ["Num_Facture", "Libelle"]:
                        v1 = str(r1.get(col, ""))
                        v2 = str(r2.get(col, ""))

                        row[f"{col}_expo"] = v1
                        row[f"{col}_users"] = v2

                        if v1 != v2:
                            has_diff = True

                    if has_diff:
                        table1_diff.append(row)
                    else:
                        table2_same.append(row)

                diff_base2["expo vs users"] = table1_diff
                lignes_identiques_base2["expo vs users"] = table2_same

            # ==========================================================
            # PHASE 5 : COMPARAISON INTER-BASE (Table2 vs Table2)
            # ==========================================================
            table2_base1 = lignes_identiques_base1.get("expo vs users", [])
            table2_base2 = lignes_identiques_base2.get("expo vs users", [])

            dict1 = {r["id"]: r for r in table2_base1}
            dict2 = {r["id"]: r for r in table2_base2}

            diff_final = []

            all_ids = set(dict1.keys()) | set(dict2.keys())

            for rid in all_ids:
                r1 = dict1.get(rid, {})
                r2 = dict2.get(rid, {})

                row = {"id": rid}
                has_diff = False

                for col in ["Num_Facture_expo", "Libelle_expo"]:
                    v1 = str(r1.get(col, ""))
                    v2 = str(r2.get(col, ""))

                    row[f"{col}_base1"] = v1
                    row[f"{col}_base2"] = v2

                    if v1 != v2:
                        has_diff = True

                if has_diff:
                    diff_final.append(row)

            tables_differences["table2_base1 vs table2_base2"] = diff_final

    # =============================
    # PHASE 6 : RENDER HTML
    # =============================
    return render_template(
        "comparaison.html",
        bases=bases_disponibles,
        all_tables_base1=tables1,
        all_tables_base2=tables2,
        tables_differences=tables_differences,
        lignes_identiques_base1=lignes_identiques_base1,
        lignes_identiques_base2=lignes_identiques_base2,
        diff_base1=diff_base1,
        diff_base2=diff_base2,
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


#  LANCEMENT DE L'APP 
if __name__ == "__main__":   
    app.run(debug=True)