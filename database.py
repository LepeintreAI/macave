# =====================================================================
#  DATABASE : sauvegarde de MaCave dans SQLite
# =====================================================================
# Les RÈGLES restent dans les classes (macave.py).
# La base de données sert uniquement à MÉMORISER, pour retrouver
# les données après un redémarrage.
#
# Chaque méthode fait toujours 2 choses, dans cet ordre :
#   1. appeler la méthode de la classe -> elle vérifie les règles
#      (si c'est refusé, une erreur est levée et RIEN n'est écrit en base)
#   2. écrire le résultat en base
# =====================================================================

import sqlite3
from datetime import date
from macave import Utilisateur, Vin, Bouteille, Etagere, Evaluation


class Database:

    def __init__(self, fichier="macave.db"):
        self.conn = sqlite3.connect(fichier)            # ouvre (ou crée) le fichier .db
        self.conn.execute("PRAGMA foreign_keys = ON")   # active les clés étrangères
        self.creer_tables()
        self.utilisateurs = {}    # tous les utilisateurs chargés : {id: Utilisateur}
        self.vins = {}            # le catalogue partagé           : {id: Vin}
        self.charger()            # on remplit ces deux dictionnaires depuis la base


    # -----------------------------------------------------------------
    #  Création des tables (une table par classe)
    # -----------------------------------------------------------------
    def creer_tables(self):
        cur = self.conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS utilisateur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant TEXT NOT NULL UNIQUE,     -- deux comptes ne peuvent pas avoir le même
            email TEXT NOT NULL,
            mot_de_passe_hash TEXT NOT NULL       -- jamais le mot de passe en clair
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS etagere (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utilisateur INTEGER NOT NULL REFERENCES utilisateur(id),   -- à qui elle appartient
            nom TEXT NOT NULL,
            capacite INTEGER NOT NULL CHECK (capacite > 0)
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS vin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domaine TEXT NOT NULL,
            nom TEXT NOT NULL,
            type_vin TEXT NOT NULL,
            millesime INTEGER NOT NULL,
            region TEXT NOT NULL,
            description TEXT,
            photo TEXT
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS bouteille (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utilisateur INTEGER NOT NULL REFERENCES utilisateur(id),   -- propriétaire
            id_vin INTEGER NOT NULL REFERENCES vin(id),                   -- quel vin
            id_etagere INTEGER REFERENCES etagere(id),                    -- vide (NULL) si archivée
            prix_achat REAL NOT NULL CHECK (prix_achat > 0),
            date_ajout TEXT NOT NULL,
            statut TEXT NOT NULL,                                         -- 'en stock' ou 'archivée'
            date_sortie TEXT
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS evaluation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_auteur INTEGER NOT NULL REFERENCES utilisateur(id),
            id_vin INTEGER NOT NULL REFERENCES vin(id),
            id_bouteille INTEGER NOT NULL REFERENCES bouteille(id),
            note INTEGER NOT NULL CHECK (note BETWEEN 0 AND 20),
            commentaire TEXT,
            date TEXT NOT NULL
        )""")

        self.conn.commit()


    # -----------------------------------------------------------------
    #  Chargement : on relit les tables et on recrée les objets Python
    # -----------------------------------------------------------------
    def charger(self):
        cur = self.conn.cursor()
        etageres = {}      # {id: Etagere}   pour retrouver l'étagère d'une bouteille
        bouteilles = {}    # {id: Bouteille} pour retrouver la bouteille d'une évaluation

        # 1. Utilisateurs (leur cave est créée automatiquement par Utilisateur)
        cur.execute("SELECT id, identifiant, email, mot_de_passe_hash FROM utilisateur")
        for id_u, identifiant, email, mdp_hash in cur.fetchall():
            u = Utilisateur(id_u, identifiant, email, "provisoire")   # mot de passe bidon...
            u.mot_de_passe_hash = mdp_hash                            # ...remplacé par le vrai hash
            self.utilisateurs[id_u] = u

        # 2. Étagères -> rangées dans la cave de leur propriétaire
        cur.execute("SELECT id, id_utilisateur, nom, capacite FROM etagere")
        for id_e, id_u, nom, capacite in cur.fetchall():
            e = Etagere(id_e, nom, capacite)
            self.utilisateurs[id_u].cave.etageres.append(e)
            etageres[id_e] = e

        # 3. Vins -> le catalogue partagé
        cur.execute("SELECT id, description, domaine, nom, type_vin, millesime, photo, region FROM vin")
        for id_v, description, domaine, nom, type_vin, millesime, photo, region in cur.fetchall():
            self.vins[id_v] = Vin(id_v, description, domaine, nom, type_vin, millesime, photo, region)

        # 4. Bouteilles -> dans la cave du propriétaire, et sur leur étagère si elles sont en stock
        cur.execute("""SELECT id, id_utilisateur, id_vin, id_etagere, prix_achat,
                              date_ajout, statut, date_sortie FROM bouteille""")
        for id_b, id_u, id_v, id_e, prix, date_ajout, statut, date_sortie in cur.fetchall():
            b = Bouteille(id_b, self.vins[id_v], prix)
            b.date_ajout = date.fromisoformat(date_ajout)   # texte "2026-10-19" -> objet date
            b.statut = statut
            if date_sortie:
                b.date_sortie = date.fromisoformat(date_sortie)
            if id_e:                                        # en stock -> on la remet sur son étagère
                etageres[id_e].ranger_bouteille(b)
            self.utilisateurs[id_u].cave.bouteilles.append(b)
            bouteilles[id_b] = b

        # 5. Évaluations -> rattachées à leur vin (pour la moyenne)
        cur.execute("SELECT id, id_auteur, id_vin, id_bouteille, note, commentaire, date FROM evaluation")
        for id_ev, id_a, id_v, id_b, note, commentaire, d in cur.fetchall():
            ev = Evaluation(id_ev, self.utilisateurs[id_a], self.vins[id_v], bouteilles[id_b], note, commentaire)
            ev.date = date.fromisoformat(d)
            self.vins[id_v].ajouter_evaluation(ev)


    # -----------------------------------------------------------------
    #  Comptes
    # -----------------------------------------------------------------
    def creer_utilisateur(self, identifiant, email, mot_de_passe):
        # Identifiant déjà pris ? (on le vérifie avant d'écrire)
        for u in self.utilisateurs.values():
            if u.identifiant == identifiant.strip():
                raise ValueError("Cet identifiant est déjà utilisé")

        u = Utilisateur(None, identifiant, email, mot_de_passe)   # vérifie email + mot de passe
        cur = self.conn.cursor()
        cur.execute("INSERT INTO utilisateur (identifiant, email, mot_de_passe_hash) VALUES (?, ?, ?)",
                    (u.identifiant, u.email, u.mot_de_passe_hash))
        self.conn.commit()

        u.id_utilisateur = cur.lastrowid     # l'id est donné par la base
        u.cave.id_cave = cur.lastrowid       # une cave par utilisateur -> même id
        self.utilisateurs[u.id_utilisateur] = u
        return u


    def connecter(self, identifiant, mot_de_passe):
        # Renvoie l'utilisateur si identifiant ET mot de passe sont bons, sinon None
        for u in self.utilisateurs.values():
            if u.identifiant == identifiant.strip() and u.verifier_mot_de_passe(mot_de_passe):
                return u
        return None


    def modifier_profil(self, u, email):
        u.modifier_profil(email)                                     # 1. règle (email valide)
        self.conn.execute("UPDATE utilisateur SET email = ? WHERE id = ?",
                          (u.email, u.id_utilisateur))                # 2. sauvegarde
        self.conn.commit()


    # -----------------------------------------------------------------
    #  Étagères
    # -----------------------------------------------------------------
    def creer_etagere(self, u, nom, capacite):
        e = u.cave.creer_etagere(nom, capacite)                      # 1. règles (R2, capacité > 0)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO etagere (id_utilisateur, nom, capacite) VALUES (?, ?, ?)",
                    (u.id_utilisateur, e.nom, e.capacite))           # 2. sauvegarde
        self.conn.commit()
        e.id_etagere = cur.lastrowid                                 # l'id vient de la base
        return e


    def modifier_capacite(self, u, e, capacite):
        u.cave.verifier_etagere(e)                                   # 1. règles (R1, R4)
        e.modifier_capacite(capacite)
        self.conn.execute("UPDATE etagere SET capacite = ? WHERE id = ?",
                          (e.capacite, e.id_etagere))                 # 2. sauvegarde
        self.conn.commit()


    def supprimer_etagere(self, u, e):
        u.cave.supprimer_etagere(e)                                  # 1. règle (R5 : étagère vide)
        self.conn.execute("DELETE FROM etagere WHERE id = ?", (e.id_etagere,))   # 2. sauvegarde
        self.conn.commit()


    # -----------------------------------------------------------------
    #  Vins : sélectionner une référence existante OU la créer (§4.2)
    # -----------------------------------------------------------------
    def trouver_ou_creer_vin(self, domaine, nom, type_vin, millesime, region, description="", photo=None):
        nouveau = Vin(None, description, domaine, nom, type_vin, millesime, photo, region)

        # Le même vin existe déjà ? (comparaison sans casse ni espaces en trop)
        for v in self.vins.values():
            if v.cle_identite() == nouveau.cle_identite():
                return v                                             # -> on réutilise l'existant

        # Sinon on l'enregistre dans le catalogue
        cur = self.conn.cursor()
        cur.execute("""INSERT INTO vin (domaine, nom, type_vin, millesime, region, description, photo)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (nouveau.domaine, nouveau.nom, nouveau.type_vin, nouveau.millesime,
                     nouveau.region, nouveau.description, nouveau.photo))
        self.conn.commit()
        nouveau.id_vin = cur.lastrowid
        self.vins[nouveau.id_vin] = nouveau
        return nouveau


    # -----------------------------------------------------------------
    #  Bouteilles
    # -----------------------------------------------------------------
    def ajouter_bouteilles(self, u, vin, etagere, quantite, prix):
        # 1. Règles : place suffisante, quantité > 0, prix > 0 (refus -> rien n'est créé)
        nouvelles = u.cave.ajouter_bouteilles(vin, etagere, quantite, prix)

        # 2. Sauvegarde en UNE transaction : "with self.conn" valide tout à la fin (commit),
        #    ou annule TOUT si une erreur arrive au milieu (rollback) -> jamais d'ajout partiel
        with self.conn:
            for b in nouvelles:
                cur = self.conn.execute(
                    """INSERT INTO bouteille (id_utilisateur, id_vin, id_etagere, prix_achat, date_ajout, statut)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (u.id_utilisateur, vin.id_vin, etagere.id_etagere, b.prix_achat,
                     b.date_ajout.isoformat(), b.statut))            # date -> texte "2026-10-19"
                b.id_bouteille = cur.lastrowid
        return nouvelles


    def modifier_bouteille(self, u, b, prix):
        u.cave.verifier_bouteille(b)                                 # 1. règles (R1, prix > 0)
        b.modifier(prix)
        self.conn.execute("UPDATE bouteille SET prix_achat = ? WHERE id = ?",
                          (b.prix_achat, b.id_bouteille))             # 2. sauvegarde
        self.conn.commit()


    def deplacer_bouteille(self, u, b, destination):
        u.cave.deplacer_bouteille(b, destination)                    # 1. règles (R1, R7)
        self.conn.execute("UPDATE bouteille SET id_etagere = ? WHERE id = ?",
                          (destination.id_etagere, b.id_bouteille))   # 2. sauvegarde
        self.conn.commit()


    def retirer_bouteille(self, u, b):
        u.cave.retirer_bouteille(b)                                  # 1. règles (R1, R8)
        self.conn.execute("DELETE FROM bouteille WHERE id = ?", (b.id_bouteille,))   # 2. sauvegarde
        self.conn.commit()


    def archiver_bouteille(self, u, b, note, commentaire=None):
        ev = u.cave.archiver_bouteille(b, note, commentaire)         # 1. règles (R1, R8, note 0..20)

        # 2. Deux écritures qui vont ensemble -> une seule transaction (les deux ou aucune)
        with self.conn:
            self.conn.execute(
                "UPDATE bouteille SET statut = ?, id_etagere = NULL, date_sortie = ? WHERE id = ?",
                (b.statut, b.date_sortie.isoformat(), b.id_bouteille))
            cur = self.conn.execute(
                """INSERT INTO evaluation (id_auteur, id_vin, id_bouteille, note, commentaire, date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (u.id_utilisateur, b.vin.id_vin, b.id_bouteille, ev.note, ev.commentaire,
                 ev.date.isoformat()))
            ev.id_evaluation = cur.lastrowid
        return ev


    # -----------------------------------------------------------------
    #  Évaluations
    # -----------------------------------------------------------------
    def modifier_evaluation(self, u, ev, note, commentaire=None):
        ev.modifier(u, note, commentaire)                            # 1. règles (R12, note 0..20)
        self.conn.execute("UPDATE evaluation SET note = ?, commentaire = ? WHERE id = ?",
                          (ev.note, ev.commentaire, ev.id_evaluation))   # 2. sauvegarde
        self.conn.commit()


    def fermer(self):
        self.conn.close()
