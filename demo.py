# =====================================================================
#  JEU DE DÉMONSTRATION (§8) — lancer avec :  python demo.py
# =====================================================================
# Recrée la base macave.db avec : 2 utilisateurs, plusieurs étagères et vins,
# des exemplaires identiques et des évaluations.
# ATTENTION : l'ancienne base est effacée.
# =====================================================================

import os
from database import Database

FICHIER = "macave.db"
if os.path.exists(FICHIER):
    os.remove(FICHIER)                              # on repart d'une base vide
db = Database(FICHIER)

# --- 2 utilisateurs ---
alice = db.creer_utilisateur("alice", "alice@exemple.fr", "alice2026")
bob = db.creer_utilisateur("bob", "bob@exemple.fr", "bob20262026")

# --- Étagères ---
a_haut = db.creer_etagere(alice, "Haut", 10)
a_bas = db.creer_etagere(alice, "Bas", 6)
a_cellier = db.creer_etagere(alice, "Cellier", 4)
b_unique = db.creer_etagere(bob, "Casier", 8)

# --- Vins du catalogue (partagé) ---
montelena = db.trouver_ou_creer_vin("Château Montelena", "Cabernet Sauvignon", "rouge", 1967, "Californie",
                                    "Le rouge vainqueur du Jugement de Paris.")
margaux = db.trouver_ou_creer_vin("Château Margaux", "Grand Vin", "rouge", 2015, "Bordeaux",
                                  "Premier grand cru classé.")
ott = db.trouver_ou_creer_vin("Domaine Ott", "Clos Mireille", "rosé", 2021, "Provence")
bollinger = db.trouver_ou_creer_vin("Bollinger", "Special Cuvée", "effervescent", 2018, "Champagne")
weinbach = db.trouver_ou_creer_vin("Domaine Weinbach", "Riesling Schlossberg", "blanc", 2019, "Alsace")

# --- Bouteilles (dont des exemplaires identiques) ---
montelena_a = db.ajouter_bouteilles(alice, montelena, a_haut, 5, 30)      # 5 identiques
db.ajouter_bouteilles(alice, margaux, a_haut, 2, 120)
db.ajouter_bouteilles(alice, ott, a_bas, 3, 25)
db.ajouter_bouteilles(alice, bollinger, a_cellier, 2, 55)
montelena_b = db.ajouter_bouteilles(bob, montelena, b_unique, 3, 32)       # même vin, autre cave
db.ajouter_bouteilles(bob, weinbach, b_unique, 2, 28)

# --- Dégustations : notes 16 (Alice), 12 et 17 (Bob) -> moyenne 15/20 ---
db.archiver_bouteille(alice, montelena_a[0], 16, "Superbe, très long en bouche.")
db.archiver_bouteille(bob, montelena_b[0], 12, "Un peu fatigué.")
db.archiver_bouteille(bob, montelena_b[1], 17, "Bien meilleur que la précédente !")

db.fermer()
print("Base de démonstration créée :", FICHIER)
print("  alice / alice2026")
print("  bob   / bob20262026")
