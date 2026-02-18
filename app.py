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
    MAIL_PASSWORD='cvwizdbmhblhznr', 
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
    
conn1 = get_db_connection("port_autonome1")
conn2 = get_db_connection("port_autonome2")
conn3 = get_db_connection("port_autonome3")

if not conn1 or not conn2:
    print("Erreur de connexion au bases")

def create_bases_table_if_not_exists(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            identifiant INT,
            nom VARCHAR(100),
            age INT,
            infos TEXT,
            statut ENUM('a_traiter', 'traite') DEFAULT 'a_traiter'
        )
    ''')
    conn.commit()

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

    all_dbs = get_all_databases_with_bases()  # récupère les bases avec table 'bases'

    for db_name in all_dbs:
        conn = get_db_connection(db_name)
        if not conn:
            continue
        cursor = conn.cursor(dictionary=True)

        # Modifier la requête pour ne pas sélectionner 'nom_base'
        try:
            cursor.execute("""
                SELECT identifiant, nom, age 
                FROM bases
                WHERE statut = 'a_traiter'
            """)
            rows = cursor.fetchall()
            # Ajoute dynamiquement le nom de la base
            for r in rows:
                r['nom_base'] = db_name
            bases_a_traiter += rows
        except mysql.connector.Error as e:
            print(f"Erreur dans {db_name} :", e)
        finally:
            conn.close()

    return render_template("index.html", bases_a_traiter=bases_a_traiter)


@app.route("/comparaison", methods=["GET", "POST"])
def comparaison():

    differences = []
    notification = ""
    champs = []

    # Connexion et récupération des bases
    bases_disponibles = get_all_databases_with_bases()

    if request.method == "POST":

        base1_name = request.form.get("base1")
        base2_name = request.form.get("base2")
        base3_name = request.form.get("base3")

        conn1 = get_db_connection(base1_name)
        conn2 = get_db_connection(base2_name)
        conn3 = get_db_connection(base3_name)

        if not conn1 or not conn2:
            flash("Impossible de se connecter à l'une des bases.", "danger")
            return redirect(url_for("comparaison"))

        cursor1 = conn1.cursor(dictionary=True)
        cursor2 = conn2.cursor(dictionary=True)

        # récupérer tables
        cursor1.execute("SHOW TABLES")
        tables1 = [list(t.values())[0] for t in cursor1.fetchall()]

        cursor2.execute("SHOW TABLES")
        tables2 = [list(t.values())[0] for t in cursor2.fetchall()]
        
        # 🚨 vérifier que chaque base possède exactement 4 tables
        
        if len(tables1) < 4 or len(tables2) < 4:
            notification = "comparaison is no dey"
            conn1.close()
            conn2.close()
            return render_template(
                "comparaison.html",
                differences=[],
                notification=notification,
                bases=bases_disponibles
                )

        
        # tables communes
        tables_communes = set(tables1) & set(tables2)

        differences_exist = False

        for table in tables_communes:

            cursor1.execute(f"SELECT * FROM {table}")
            rows1 = cursor1.fetchall()

            cursor2.execute(f"SELECT * FROM {table}")
            rows2 = cursor2.fetchall()

            # ⚠️ éviter crash si table vide
            if rows1:
                champs = [c for c in rows1[0].keys() if c != "id"]
            elif rows2:
                champs = [c for c in rows2[0].keys() if c != "id"]
            else:
                continue

            dict1 = {r['identifiant']: r for r in rows1 if 'identifiant' in r}
            dict2 = {r['identifiant']: r for r in rows2 if 'identifiant' in r}

            all_ids = sorted(set(dict1.keys()) | set(dict2.keys()))

            for ident in all_ids:

                r1 = dict1.get(ident)
                r2 = dict2.get(ident)

                if r1 and r2:
                    has_diff = any(r1[c] != r2[c] for c in champs)
                else:
                    has_diff = True

                if has_diff:

                    differences_exist = True

                    diff_row = {
                        "table": table,
                        "identifiant": ident
                    }

                    for champ in champs:
                        diff_row[f"base1_{champ}"] = r1.get(champ) if r1 else ""
                        diff_row[f"base2_{champ}"] = r2.get(champ) if r2 else ""

                    differences.append(diff_row)

        # ✅ si aucune différence → afficher toutes les lignes fusionnées
        if not differences_exist:

            for table in tables_communes:

                cursor1.execute(f"SELECT * FROM {table}")
                rows1 = cursor1.fetchall()

                cursor2.execute(f"SELECT * FROM {table}")
                rows2 = cursor2.fetchall()

                dict1 = {r['identifiant']: r for r in rows1 if 'identifiant' in r}
                dict2 = {r['identifiant']: r for r in rows2 if 'identifiant' in r}

                all_ids = sorted(set(dict1.keys()) | set(dict2.keys()))

                for ident in all_ids:

                    r1 = dict1.get(ident)
                    r2 = dict2.get(ident)

                    diff_row = {
                        "table": table,
                        "identifiant": ident
                    }

                    for champ in champs:
                        diff_row[f"base1_{champ}"] = r1.get(champ) if r1 else ""
                        diff_row[f"base2_{champ}"] = r2.get(champ) if r2 else ""

                    differences.append(diff_row)

            notification = "✅ Aucune différence"

        else:
            notification = f"{len(differences)} différence(s) trouvée(s)"

        conn1.close()
        conn2.close()

    return render_template(
        "comparaison.html",
        differences=differences,
        notification=notification,
        bases=bases_disponibles
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

        # Vérifier que les champs obligatoires sont remplis
        if not nom_table or not identifiant or not nom or not age:
            flash("Veuillez remplir tous les champs obligatoires !", "danger")
            return redirect(url_for("ajouter"))

        # Créer la base si elle n'existe pas
        conn = get_or_create_db(nom_base)
        if not conn:
            flash(f"Erreur : impossible de se connecter ou créer la base '{nom_base}' !", "danger")
            return redirect(url_for("ajouter"))

        cursor = conn.cursor(dictionary=True)

        # Créer la table 'bases' si elle n'existe pas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                identifiant INT,
                nom VARCHAR(100),
                age INT,
                infos TEXT,
                statut ENUM('a_traiter','traite') DEFAULT 'a_traiter'
            )
        """)
        conn.commit()

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
            "INSERT INTO bases (identifiant, nom, age, infos) VALUES (%s, %s, %s, %s)",
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