
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import os
import smtplib
from flask_mail import Mail, Message
import pandas as pd 
from decimal import Decimal
from itertools import zip_longest 


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
        
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
        conn.close()

        
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
    valid_dbs = []  
    try:
        
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password=""
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = [db[0] for db in cursor.fetchall()]

        for db_name in dbs:
            
            if db_name in ["information_schema", "mysql", "performance_schema", "phpmyadmin", "test"]:
                continue

            conn_db = None
            try:
                
                
                conn_db = mysql.connector.connect(
                    host="localhost",
                    user="root",
                    password="",
                    database=db_name
                )
                cursor_db = conn_db.cursor()
                cursor_db.execute("SHOW TABLES")  
                tables = cursor_db.fetchall()

                if tables:  
                    valid_dbs.append(db_name)

            except mysql.connector.Error:
                continue  
            finally:
                if conn_db:
                    conn_db.close()  

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



@app.route('/notifier', methods=['POST'])
def notifier():
    data = request.get_json()

    differences = data.get("differences", [])
    base1 = data.get("base1", "base1")
    base2 = data.get("base2", "base2")

    
    emails_par_type = {
        "VIDE": "garbamoha8@gmail.com",
        "Erreur": "garbamohamedseidoul@gmail.com"
    }

    try:
        
        diffs_par_type = {}
        for diff in differences:
            
            types_ligne = set()
            for k, v in diff.items():
                if str(v) == "VIDE":
                    types_ligne.add("VIDE")
                elif str(v) == "Erreur":
                    types_ligne.add("Erreur")
            
            if not types_ligne:
                continue
            for t in types_ligne:
                diffs_par_type.setdefault(t, []).append(diff)

        
        for erreur_type, diffs in diffs_par_type.items():
            if not diffs:
                continue
            
            df = pd.DataFrame(diffs)
            
            df.columns = [
                col.replace("base1_", f"{base1}_").replace("base2_", f"{base2}_")
                for col in df.columns
            ]
            excel_file = f"notification_{erreur_type}.xlsx"
            df.to_excel(excel_file, index=False)

            msg = Message(
                subject=f"Notification erreurs {erreur_type}",
                sender=app.config['MAIL_USERNAME'],
                recipients=[emails_par_type[erreur_type]],
                body=f"Bonjour,\n\nVeuillez trouver ci-joint le tableau des erreurs '{erreur_type}' détectées.\n\nCordialement."
            )

            with open(excel_file, "rb") as f:
                msg.attach(
                    excel_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f.read()
                )

            mail.send(msg)
            print(f"Mail envoyé à {emails_par_type[erreur_type]} avec {len(diffs)} erreurs {erreur_type}")

        return jsonify({"status": "success", "message": f"{len(differences)} différences envoyées avec succès"})

    except Exception as e:
        print("ERREUR MAIL :", e)
        return jsonify({"status": "error", "message": str(e)}), 500


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
    
    row_base1 = {}
    row_base2 = {}
    row_result = {}

    if request.method == "POST":
        base1_name = request.form.get("base1")
        base2_name = request.form.get("base2")
        table1_name = request.form.get("table1")
        table2_name = request.form.get("table2")
        colonnes_base1 = request.form.getlist("colonnes_base1")
        colonnes_base2 = request.form.getlist("colonnes_base2")

        
        
        # La comparaison entre deux base
        if base1_name and base2_name and table1_name and table2_name and colonnes_base1 and colonnes_base2:

            conn1 = get_db_connection(base1_name)
            conn2 = get_db_connection(base2_name)
            cursor1 = conn1.cursor(dictionary=True)
            cursor2 = conn2.cursor(dictionary=True)

            cursor1.execute(f"SELECT * FROM {table1_name}")
            rows_base1 = cursor1.fetchall()
            cursor2.execute(f"SELECT * FROM {table2_name}")
            rows_base2 = cursor2.fetchall()

            conn1.close()
            conn2.close()

            base1_dict = {r['id']: r for r in rows_base1}
            base2_dict = {r['id']: r for r in rows_base2}

            all_ids = set(base1_dict.keys()) | set(base2_dict.keys())

            diff_final = []

            
            nb_absent_base1 = 0
            nb_absent_base2 = 0
            nb_diff = 0

            for id_val in sorted(all_ids):
                row_base1 = base1_dict.get(id_val, {})
                row_base2 = base2_dict.get(id_val, {})

                row_result = {}

                id_base1_val = str(row_base1.get('id', 'VIDE')).strip()
                id_base2_val = str(row_base2.get('id', 'VIDE')).strip()

                ids_identiques = (id_base1_val == id_base2_val)

                row_result['id_base1'] = '' if ids_identiques else id_base1_val
                row_result['id_base2'] = '' if ids_identiques else id_base2_val

                has_diff = False

                for col1, col2 in zip_longest(colonnes_base1, colonnes_base2, fillvalue=None):
                    val1 = str(row_base1.get(col1, 'VIDE')) if col1 else 'VIDE'
                    val2 = str(row_base2.get(col2, 'VIDE')) if col2 else 'VIDE'

                    if col1:
                        row_result[f"{col1}_base1"] = val1
                    if col2:
                        row_result[f"{col2}_base2"] = val2

                    if val1 != val2:
                        has_diff = True

                
                if not row_base1:
                    nb_absent_base1 += 1
                elif not row_base2:
                    nb_absent_base2 += 1
                elif has_diff:
                    nb_diff += 1

                if has_diff or not row_base1 or not row_base2:
                    diff_final.append(row_result)

            if diff_final:
                tables_differences[f"{table1_name} vs {table2_name}"] = diff_final

            
            messages = []

            if nb_absent_base1:
                messages.append(f"{nb_absent_base1} ID(s) absents dans base1")

            if nb_absent_base2:
                messages.append(f"{nb_absent_base2} ID(s) absents dans base2")

            if nb_diff:
                messages.append(f"{nb_diff} ligne(s) avec différences")

            if not messages:
                notification = "Aucune différence détectée"
            else:
                notification = " | ".join(messages)

        elif base1_name and not base2_name and table1_name and colonnes_base1:

            conn1 = get_db_connection(base1_name)
            cursor1 = conn1.cursor(dictionary=True)

            
            cursor1.execute(f"SELECT * FROM {table1_name}")
            rows1 = cursor1.fetchall()

            
            cursor1.execute(f"SHOW COLUMNS FROM {table1_name}")
            type_expected = {}
            for col_info in cursor1.fetchall():
                field = col_info['Field']
                type_mysql = col_info['Type'].lower()

                if 'int' in type_mysql or 'tinyint' in type_mysql:
                    type_expected[field] = "int"
                elif 'decimal' in type_mysql or 'float' in type_mysql or 'double' in type_mysql:
                    type_expected[field] = "float"
                else:
                    if field in ["age"]:
                        type_expected[field] = "int"
                    elif field in ["salaire"]:
                        type_expected[field] = "float"
                    else:
                        type_expected[field] = "str"

            
            conn1.close()

            resultats = []

            
            nb_vides = 0
            nb_erreurs_type = 0

            
            for r in rows1:
                row_result = {"id": r.get("id")}
                statuts = {}

                for col in colonnes_base1:
                    expected_type = type_expected.get(col, "str")
                    v = r.get(col)

                    if v is None:
                        statut = "VIDE"
                        nb_vides += 1
                    else:
                        if expected_type == "int":
                            try:
                                int(str(v).strip())
                                statut = " "
                            except:
                                statut = "Erreur"
                                nb_erreurs_type += 1
                        elif expected_type == "float":
                            try:
                                float(str(v).strip())
                                statut = " "
                            except:
                                statut = "Erreur"
                                nb_erreurs_type += 1
                        else:
                            statut = " "

                    row_result[col] = v if v is not None else "VIDE"
                    row_result[f"statut_{col}"] = statut
                    statuts[f"statut_{col}"] = statut

                resultats.append(row_result)

            if nb_vides or nb_erreurs_type:
                tables_differences[f"{table1_name} (vérification mono-base)"] = resultats

                
                diffs_par_type = {
                    "VIDE": [],
                    "TYPE": []
                }

                for r in resultats:
                    for col_statut, statut in r.items():
                        if col_statut.startswith("statut_"):
                            if statut == "VIDE":
                                diffs_par_type["VIDE"].append(r)
                            elif statut == "Erreur":
                                diffs_par_type["TYPE"].append(r)

                emails_par_type = {
                    "VIDE": "garbamoha8@gmail.com",
                    "TYPE": "garbamohamedseidoul@gmail.com"
                }

                for typ, rows in diffs_par_type.items():
                    if not rows:
                        continue
                    df = pd.DataFrame(rows)
                    excel_file = f"notification_{typ}.xlsx"
                    df.to_excel(excel_file, index=False)

                    msg = Message(
                        subject=f"Notification des erreurs {typ} : {table1_name}",
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[emails_par_type[typ]],
                        body=f"Bonjour,\n\nVeuillez trouver ci-joint le tableau des erreurs {typ} détectées pour {table1_name}.\n\nCordialement."
                    )
                    with open(excel_file, "rb") as f:
                        msg.attach("notification.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f.read())
                    mail.send(msg)
                    print(f"Mail envoyé à {emails_par_type[typ]} avec {len(rows)} erreurs {typ}")

    return render_template(
        "comparaison.html",
        bases=bases_disponibles,
        tables_differences=tables_differences,
        notification=notification
    )
    
    

def get_tables(db_name):
    conn = get_db_connection(db_name)
    if not conn: return [ ]
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]
    conn.close()
    return tables



def get_colonnes(db_name, table_name):
    conn = get_db_connection(db_name)
    if not conn: return []
    cursor = conn.cursor()
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    colonnes = [c[0] for c in cursor.fetchall()]
    conn.close()
    return colonnes

@app.route("/get_tables")
def api_get_tables():
    base = request.args.get("base")
    return jsonify({"tables": get_tables(base)})



@app.route("/get_colonnes")
def api_get_colonnes():
    base = request.args.get("base")
    table = request.args.get("table")
    return jsonify({"colonnes": get_colonnes(base, table)})


@app.route("/ajouter", methods=["GET", "POST"])
def ajouter():
    
    bases_disponibles = get_all_databases_with_bases()

    
    base_defaut = bases_disponibles[0] if bases_disponibles else None
    tables_existantes = get_tables_for_db(base_defaut) if base_defaut else []

    if request.method == "POST":
        
        nom_base_select = request.form.get("nom_base_select")
        nom_base_new = request.form.get("nom_base_new")

        
        if nom_base_new:
            nom_base = nom_base_new
        elif nom_base_select:
            nom_base = nom_base_select
        else:
            flash("Veuillez choisir ou créer une base !", "danger")
            return redirect(url_for("ajouter"))

        nom_table = request.form.get("nom_table")
        identifiant = request.form.get("identifiant")
        num_facture = request.form.get("Num_Facture")
        libelle = request.form.get("Libelle")

        
        conn = get_or_create_db(nom_base)
        if not conn:
            flash(f"Erreur : impossible de se connecter ou créer la base '{nom_base}' !", "danger")
            return redirect(url_for("ajouter"))

        cursor = conn.cursor(dictionary=True)

        
        cursor.execute(f"SHOW TABLES LIKE %s", (nom_table,))
        if not cursor.fetchone():
            
            cursor.execute(f"""
                CREATE TABLE {nom_table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    identifiant INT,
                    Num_Facture VARCHAR(100),
                    Libelle VARCHAR(255)
                )
            """)
            conn.commit()

        
        cursor.execute(
            f"INSERT INTO `{nom_table}` (identifiant, Num_Facture, Libelle) VALUES (%s, %s, %s)",
            (identifiant, num_facture, libelle)
        )
        conn.commit()
        conn.close()

        flash(f"Base '{nom_base}' et table '{nom_table}' créées avec succès !", "success")
        return redirect(url_for("index"))

    
    return render_template("ajouter.html", bases=bases_disponibles, tables=tables_existantes)



def get_tables_for_db(nom_base):
    """
    Récupère la liste des tables existantes pour une base donnée.
    """
    conn = get_or_create_db(nom_base)
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

#  LANCEMENT DE L'APPLI 
if __name__ == "__main__":   
    app.run(debug=True)