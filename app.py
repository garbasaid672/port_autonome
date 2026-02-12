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
DATABASE = r"C:\Users\GARBA\Desktop\port_autonome\database.db"

mail = Mail(app)
app.secret_key = "secret123"

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",          # ton utilisateur MySQL
            password="",          # ton mot de passe MySQL
            database="port_autonome"
        )
        return conn
    except mysql.connector.Error as e:
        print("Erreur de connexion MySQL :", e)
        return None




def init_db():
    conn = get_db_connection()
    if not conn:
        print("Erreur de connexion à MySQL")
        return

    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bases (
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
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Utilise 'identifiant' et pas 'id' pour afficher ce que l'utilisateur saisit
    cursor.execute("SELECT identifiant, nom, age, infos, statut, nom_base FROM bases WHERE statut = 'a_traiter'")
    bases_a_traiter = cursor.fetchall()

    cursor.execute("SELECT identifiant, nom, age, infos, statut, nom_base FROM bases WHERE statut = 'traite'")
    bases_traite = cursor.fetchall()

    conn.close()
    return render_template("index.html", bases_a_traiter=bases_a_traiter, bases_traite=bases_traite)








@app.route("/comparaison", methods=["GET", "POST"])
def comparaison():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # obligatoire pour accéder aux colonnes par nom

    cursor.execute("SELECT * FROM bases")
    bases = cursor.fetchall()

    differences = []
    notification = ""

    if request.method == "POST":
        base1_id = request.form.get("base1")
        base2_id = request.form.get("base2")

        cursor.execute("SELECT * FROM bases WHERE id = %s", (base1_id,))
        base1 = cursor.fetchone()

        cursor.execute("SELECT * FROM bases WHERE id = %s", (base2_id,))
        base2 = cursor.fetchone()

        champs = ["identifiant", "nom", "age", "infos"] # colonnes correctes
        for champ in champs:
            v1 = base1[champ]
            v2 = base2[champ]
            if v1 != v2:
                differences.append({
                    "champ": champ,
                    "base1": v1,
                    "base2": v2
                })

        notification = f"{len(differences)} différence(s) détectée(s)"

    conn.close()
    return render_template("comparaison.html", bases=bases, differences=differences, notification=notification)




@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    if request.method == "POST":
        try:
            nom_base = request.form["nom_base"]
            identifiant = int(request.form["identifiant"])  # récupère le champ du formulaire
            nom = request.form["nom"]
            age = int(request.form["age"])
            infos = request.form["infos"]

            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO bases (nom_base, identifiant, nom, age, infos, statut) VALUES (%s, %s, %s, %s, %s, %s)",
                (nom_base, identifiant, nom, age, infos, 'a_traiter')
            )
            conn.commit()
            conn.close()

            flash("Base ajoutée avec succès !", "success")
            return redirect(url_for("index"))

        except Exception as e:
            print("❌ ERREUR INSERTION :", e)
            flash(f"Erreur : {e}", "danger")

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