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
            # Exclure les bases système
            if db_name in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                continue

            # Vérifier si la base contient au moins une table pertinente (bases, table1, table2, navires)
            try:
                conn_db = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",
                    database=db_name
                )
                cursor_db = conn_db.cursor()
                cursor_db.execute("SHOW TABLES")
                tables = [t[0].lower() for t in cursor_db.fetchall()]
                relevant_tables = {'bases', 'table1', 'table2', 'navires', 'quais'}
                if any(t in relevant_tables for t in tables) or len(tables) >= 2:
                    valid_dbs.append(db_name)
                conn_db.close()
            except:
                continue
        conn.close()
        return valid_dbs
    except mysql.connector.Error as e:
        print("Erreur MySQL :", e)
        return []


def ensure_table_names(database_name):
    conn = get_db_connection(database_name)
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]

    if len(tables) < 2:
        conn.close()
        return tables

    # Case 1: Both already exist
    if "table1" in tables and "table2" in tables:
        conn.close()
        return ["table1", "table2"]

    # Mapping to target names
    target_names = ["table1", "table2"]
    used_indices = []

    # Identify if some are already correctly named
    if "table1" in tables:
        used_indices.append(tables.index("table1"))
    if "table2" in tables:
        used_indices.append(tables.index("table2"))

    # Assign remaining target names to existing tables that are not correctly named
    for target in target_names:
        if target not in tables:
            # Pick a table that is NOT in target_names and NOT already used
            for i, current_name in enumerate(tables):
                if current_name not in target_names and i not in used_indices:
                    cursor.execute(f"RENAME TABLE `{current_name}` TO `{target}`")
                    used_indices.append(i)
                    break

    conn.commit()
    conn.close()
    return ["table1", "table2"]


def process_internal_comparison(database_name):
    conn = get_db_connection(database_name)
    if not conn:
        return
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Get common columns (excluding id)
        cursor.execute("SHOW COLUMNS FROM `table1`")
        cols1 = [row['Field'] for row in cursor.fetchall() if row['Field'] != 'id']
        cursor.execute("SHOW COLUMNS FROM `table2`")
        cols2 = [row['Field'] for row in cursor.fetchall() if row['Field'] != 'id']

        common_cols = list(set(cols1) & set(cols2))
        if not common_cols:
            conn.close()
            return

        # 2. IDENTIFY IDENTICAL ROWS (INTERSECTION)
        join_cond = " AND ".join([f"t1.`{c}` = t2.`{c}`" for c in common_cols])

        # We need to KEEP only rows in table2 that have a match in table1
        # AND we need to REMOVE rows from table1 that have a match in table2
        # (since table1 should only have non-identical info)

        # Identify rows in table1 that ARE in table2 (to remove from table1)
        cursor.execute(f"SELECT t1.id FROM `table1` t1 INNER JOIN `table2` t2 ON {join_cond}")
        identical_in_t1 = [row['id'] for row in cursor.fetchall()]

        # Identify rows in table2 that are NOT in table1 (to move to table1)
        cursor.execute(f"SELECT t2.* FROM `table2` t2 LEFT JOIN `table1` t1 ON {join_cond} WHERE t1.`{common_cols[0]}` IS NULL")
        to_move_from_t2 = cursor.fetchall()

        # 3. EXECUTE CHANGES

        # Remove identical from table1
        if identical_in_t1:
            placeholders = ", ".join(["%s"] * len(identical_in_t1))
            cursor.execute(f"DELETE FROM `table1` WHERE id IN ({placeholders})", tuple(identical_in_t1))

        # Move non-identical from table2 to table1
        if to_move_from_t2:
            for row in to_move_from_t2:
                # Insert into table1 (exclude id)
                row_to_insert = {k: v for k, v in row.items() if k in cols1}
                if row_to_insert:
                    fields = ", ".join([f"`{k}`" for k in row_to_insert.keys()])
                    placeholders = ", ".join(["%s"] * len(row_to_insert))
                    values = tuple(row_to_insert.values())
                    cursor.execute(f"INSERT INTO `table1` ({fields}) VALUES ({placeholders})", values)

                # Delete from table2
                if 'id' in row:
                    cursor.execute("DELETE FROM `table2` WHERE id = %s", (row['id'],))
                else:
                    where_cond = " AND ".join([f"`{c}` = %s" for c in row.keys()])
                    cursor.execute(f"DELETE FROM `table2` WHERE {where_cond}", tuple(row.values()))

        conn.commit()
    except mysql.connector.Error as e:
        print(f"Erreur Phase 1 ({database_name}): {e}")
        conn.rollback()
    finally:
        conn.close()


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
    differences = []
    notification = ""
    phase1_summary = {}

    bases_disponibles = get_all_databases_with_bases()

    if request.method == "POST":
        base1_name = request.form.get("base1")
        base2_name = request.form.get("base2")

        # PHASE 1 : Renommer et comparer en interne
        for b_name in [base1_name, base2_name]:
            tables = ensure_table_names(b_name)
            if tables and "table1" in tables and "table2" in tables:
                process_internal_comparison(b_name)
                phase1_summary[b_name] = "Traitement Phase 1 terminé"
            else:
                phase1_summary[b_name] = "Phase 1 : tables insuffisantes"

        # PHASE 2 : Comparer base1.table2 et base2.table2
        conn1 = get_db_connection(base1_name)
        conn2 = get_db_connection(base2_name)

        if conn1 and conn2:
            cursor1 = conn1.cursor(dictionary=True)
            cursor2 = conn2.cursor(dictionary=True)

            # On vérifie l'existence de table2 dans les deux
            cursor1.execute("SHOW TABLES LIKE 'table2'")
            exists1 = cursor1.fetchone()
            cursor2.execute("SHOW TABLES LIKE 'table2'")
            exists2 = cursor2.fetchone()

            if exists1 and exists2:
                cursor1.execute("SELECT * FROM `table2`")
                rows1 = cursor1.fetchall()
                cursor2.execute("SELECT * FROM `table2`")
                rows2 = cursor2.fetchall()

                # Identify matching columns (excluding id)
                cursor1.execute("SHOW COLUMNS FROM `table2`")
                champs1 = [row['Field'] for row in cursor1.fetchall() if row['Field'] != 'id']
                cursor2.execute("SHOW COLUMNS FROM `table2`")
                champs2 = [row['Field'] for row in cursor2.fetchall() if row['Field'] != 'id']
                common_champs = list(set(champs1) & set(champs2))

                if not common_champs:
                    notification = "Erreur : aucun champ commun entre les deux 'table2'"
                else:
                    # Comparison logic: Try to match rows from DB1 in DB2 based on common fields
                    # Any row in DB1 not found in DB2 is a difference
                    # Any row in DB2 not found in DB1 is a difference

                    def make_key(row):
                        return tuple(row.get(c) for c in common_champs)

                    set1 = {make_key(r): r for r in rows1}
                    set2 = {make_key(r): r for r in rows2}

                    all_keys = sorted(list(set(set1.keys()) | set(set2.keys())))

                    idx = 1
                    for k in all_keys:
                        r1 = set1.get(k)
                        r2 = set2.get(k)

                        if r1 is None or r2 is None:
                            # One side is missing the entire record
                            row_diff_base1 = []
                            row_diff_base2 = []
                            for c in common_champs:
                                v1 = r1.get(c, "—") if r1 else "—"
                                v2 = r2.get(c, "—") if r2 else "—"
                                if v1 != v2:
                                    row_diff_base1.append(f"{c}: {v1}")
                                    row_diff_base2.append(f"{c}: {v2}")

                            differences.append({
                                "ligne": idx,
                                "base1": ", ".join(row_diff_base1),
                                "base2": ", ".join(row_diff_base2)
                            })
                            idx += 1
                        else:
                            # Both sides have the record (based on common fields as key, it should be identical if k is unique)
                            # If there are OTHER fields (not in common_champs), they might differ
                            pass
            else:
                notification = "Erreur : 'table2' manquante dans l'une des bases"

            conn1.close()
            conn2.close()

        notification = "Comparaison terminée"

    return render_template("comparaison.html",
                           differences=differences,
                           notification=notification,
                           bases=bases_disponibles,
                           phase1_summary=phase1_summary)





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