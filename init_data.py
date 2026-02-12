import mysql.connector
from datetime import datetime

# Connexion à MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",       # ton utilisateur MySQL
    "password": "",       # ton mot de passe MySQL
    "database": "port_autonome",  # la base MySQL
    "port": 3306
}

def init_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Table pour stocker les bases
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom_base VARCHAR(255),
            valeur1 INT,
            valeur2 INT,
            valeur3 INT,
            valeur4 INT,
            date_update DATETIME
        )
        """)

        # Table pour stocker les données
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS donnees (
            id INT,
            nom VARCHAR(255),
            valeur INT,
            nom_base VARCHAR(255)
        )
        """)

        # Table pour stocker les comparaisons
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS comparaison (
            id INT AUTO_INCREMENT PRIMARY KEY,
            base1_id INT,
            base2_id INT,
            has_difference BOOLEAN,
            date_compared DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Table pour stocker les notifications
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            contenu TEXT,
            date_envoi DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        conn.close()
        print("✅ Base de données MySQL initialisée avec succès")

    except mysql.connector.Error as err:
        print("❌ ERREUR MYSQL :", err)

if __name__ == "__main__":
    init_db()
    
    
    import mysql.connector
from datetime import datetime

# Connexion à MySQL
DB_CONFIG = {
    "host": "localhost",
    "user": "root",       # ton utilisateur MySQL
    "password": "",       # ton mot de passe MySQL
    "database": "port_autonome",
    "port": 3306
}

def init_db():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Table navires
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS navires (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom_navire VARCHAR(255),
            type_navire VARCHAR(100),
            tonnage INT,
            date_arrivee DATETIME
        )
        """)

        # Table quais
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS quais (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nom_quai VARCHAR(100),
            longueur INT,
            profondeur INT,
            status ENUM('libre','occupe') DEFAULT 'libre'
        )
        """)

        # Table mouvements
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mouvements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            id_navire INT,
            id_quai INT,
            date_operation DATETIME,
            type_operation ENUM('chargement','dechargement'),
            volume INT,
            FOREIGN KEY (id_navire) REFERENCES navires(id),
            FOREIGN KEY (id_quai) REFERENCES quais(id)
        )
        """)

        conn.commit()
        conn.close()
        print("✅ Base de données MySQL initialisée avec succès")

    except mysql.connector.Error as err:
        print("❌ ERREUR MYSQL :", err)

if __name__ == "__main__":
    init_db()

