# =====================================================================
#  TESTS AUTOMATISÉS (§7.1) — lancer avec :  pytest
# =====================================================================
# Chaque fonction qui commence par test_ est un test.
# assert <condition> : si la condition est fausse, pytest signale un ÉCHEC.
# pytest.raises(Erreur) : le test réussit SEULEMENT si l'erreur est bien levée.
# =====================================================================

import os
import sys
import pytest

# Permet d'importer macave.py, database.py et app.py depuis le dossier parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from macave import Utilisateur, Vin
from database import Database


# ---------------------------------------------------------------------
#  Fixtures : des objets prêts à l'emploi, recréés NEUFS pour chaque test
# ---------------------------------------------------------------------
@pytest.fixture
def alice():
    return Utilisateur(1, "alice", "alice@mail.fr", "motdepasse123")


@pytest.fixture
def montelena():
    return Vin(1, "", "Château Montelena", "Cabernet Sauvignon", "rouge", 1967, None, "Californie")


# =====================================================================
#  Les 5 tests demandés par le sujet
# =====================================================================

def test_depassement_de_capacite_refuse_sans_ajout_partiel(alice, montelena):
    # Scénario : ajouter 6 bouteilles à une étagère occupée à 5/10
    haut = alice.cave.creer_etagere("Haut", 10)
    alice.cave.ajouter_bouteilles(montelena, haut, 5, 30)
    with pytest.raises(ValueError):
        alice.cave.ajouter_bouteilles(montelena, haut, 6, 30)
    assert haut.occupation() == 5                       # aucun ajout partiel
    assert len(alice.cave.bouteilles_en_stock()) == 5


def test_retrait_d_un_exemplaire_parmi_cinq(alice, montelena):
    # R6 : retirer 1 bouteille parmi 5 en laisse 4 ; le vin reste au catalogue
    haut = alice.cave.creer_etagere("Haut", 10)
    bouteilles = alice.cave.ajouter_bouteilles(montelena, haut, 5, 30)
    alice.cave.retirer_bouteille(bouteilles[0])
    assert len(alice.cave.bouteilles_en_stock()) == 4
    assert haut.occupation() == 4
    assert alice.cave.historique() == []                # pas d'historique pour un retrait
    assert montelena.nom == "Cabernet Sauvignon"        # l'objet vin n'est pas touché


def test_deplacement_met_a_jour_les_deux_etageres(alice, montelena):
    haut = alice.cave.creer_etagere("Haut", 10)
    bas = alice.cave.creer_etagere("Bas", 1)
    b1, b2 = alice.cave.ajouter_bouteilles(montelena, haut, 2, 30)
    alice.cave.deplacer_bouteille(b1, bas)
    assert haut.occupation() == 1 and bas.occupation() == 1
    assert b1.etagere is bas
    # R7 : déplacement vers une étagère pleine refusé, et rien ne bouge
    with pytest.raises(ValueError):
        alice.cave.deplacer_bouteille(b2, bas)
    assert b2.etagere is haut and haut.occupation() == 1


def test_archivage_d_un_exemplaire_parmi_cinq(alice, montelena):
    haut = alice.cave.creer_etagere("Haut", 10)
    bouteilles = alice.cave.ajouter_bouteilles(montelena, haut, 5, 30)
    ev = alice.cave.archiver_bouteille(bouteilles[0], 16, "Superbe")
    assert len(alice.cave.bouteilles_en_stock()) == 4   # 4 en stock
    assert len(alice.cave.historique()) == 1            # 1 dans l'historique
    assert haut.occupation() == 4                       # n'occupe plus de place
    assert ev.auteur is alice and ev.vin is montelena and ev.bouteille is bouteilles[0]   # R11
    # R8 : impossible d'archiver ou de retirer une seconde fois
    with pytest.raises(ValueError):
        alice.cave.archiver_bouteille(bouteilles[0], 10)
    with pytest.raises(ValueError):
        alice.cave.retirer_bouteille(bouteilles[0])


def test_moyenne_communautaire(alice, montelena):
    assert montelena.note_moyenne() is None             # « Non évalué », pas 0
    haut = alice.cave.creer_etagere("Haut", 10)
    bouteilles = alice.cave.ajouter_bouteilles(montelena, haut, 3, 30)
    notes = [16, 12, 17]
    evaluations = [alice.cave.archiver_bouteille(b, n) for b, n in zip(bouteilles, notes)]
    assert montelena.note_moyenne() == 15               # (16 + 12 + 17) / 3
    evaluations[1].modifier(alice, 18)                  # 12 -> 18
    assert montelena.note_moyenne() == 17               # la modification est répercutée


# =====================================================================
#  Tests complémentaires : données invalides, doublons, contrôle d'accès,
#  persistance après redémarrage
# =====================================================================

def test_donnees_invalides_refusees(alice, montelena):
    with pytest.raises(ValueError):
        alice.cave.creer_etagere("Haut", 0)                         # capacité > 0
    haut = alice.cave.creer_etagere("Haut", 10)
    with pytest.raises(ValueError):
        alice.cave.creer_etagere("  HAUT ", 5)                      # R2 : nom unique
    with pytest.raises(ValueError):
        alice.cave.ajouter_bouteilles(montelena, haut, 1, -5)       # prix > 0
    with pytest.raises(ValueError):
        alice.cave.ajouter_bouteilles(montelena, haut, 0, 30)       # quantité > 0
    b = alice.cave.ajouter_bouteilles(montelena, haut, 1, 30)[0]
    with pytest.raises(ValueError):
        alice.cave.archiver_bouteille(b, 25)                        # note de 0 à 20
    assert b.est_en_stock()                                         # rien n'a bougé
    with pytest.raises(ValueError):
        Vin(2, "", "X", "Y", "bière", 2020, None, "Z")              # type autorisé
    with pytest.raises(ValueError):
        haut.modifier_capacite(0)


def test_etagere_non_vide_ne_peut_pas_etre_supprimee(alice, montelena):
    haut = alice.cave.creer_etagere("Haut", 10)
    alice.cave.ajouter_bouteilles(montelena, haut, 1, 30)
    with pytest.raises(ValueError):
        alice.cave.supprimer_etagere(haut)                          # R5
    with pytest.raises(ValueError):
        haut.modifier_capacite(0)                                   # R4


def test_doublon_de_vin_detecte(montelena):
    autre = Vin(2, "", "  château  MONTELENA ", "cabernet sauvignon", "Rouge", 1967, None, "californie ")
    assert autre.cle_identite() == montelena.cle_identite()
    autre_millesime = Vin(3, "", "Château Montelena", "Cabernet Sauvignon", "rouge", 1968, None, "Californie")
    assert autre_millesime.cle_identite() != montelena.cle_identite()


def test_controle_d_acces_entre_utilisateurs(alice, montelena):
    bob = Utilisateur(2, "bob", "bob@mail.fr", "azertyuiop")
    haut = alice.cave.creer_etagere("Haut", 10)
    b = alice.cave.ajouter_bouteilles(montelena, haut, 1, 30)[0]
    assert not bob.possede(alice.cave)                              # R1
    with pytest.raises(PermissionError):
        bob.cave.archiver_bouteille(b, 10)                          # bouteille d'Alice
    ev = alice.cave.archiver_bouteille(alice.cave.ajouter_bouteilles(montelena, haut, 1, 30)[0], 14)
    with pytest.raises(PermissionError):
        ev.modifier(bob, 0)                                         # R12


def test_persistance_apres_redemarrage(tmp_path):
    fichier = str(tmp_path / "test.db")                 # base temporaire, effacée après le test
    db = Database(fichier)
    alice = db.creer_utilisateur("alice", "alice@mail.fr", "motdepasse123")
    haut = db.creer_etagere(alice, "Haut", 10)
    vin = db.trouver_ou_creer_vin("Château Montelena", "Cabernet Sauvignon", "rouge", 1967, "Californie")
    bouteilles = db.ajouter_bouteilles(alice, vin, haut, 5, 30)
    db.archiver_bouteille(alice, bouteilles[0], 16)
    db.fermer()

    db = Database(fichier)                              # « redémarrage » : tout est relu en base
    alice = db.connecter("alice", "motdepasse123")
    assert alice is not None
    assert len(alice.cave.bouteilles_en_stock()) == 4
    assert len(alice.cave.historique()) == 1
    assert alice.cave.etageres[0].occupation() == 4
    assert list(db.vins.values())[0].note_moyenne() == 16
    assert db.connecter("alice", "mauvais") is None
    db.fermer()


def test_pages_web_protegees(tmp_path):
    import app as application
    application.db = Database(str(tmp_path / "web.db"))   # l'appli utilise une base de test
    client = application.app.test_client()

    # Non connecté : redirection vers la connexion (contrôle côté serveur)
    assert client.get("/stock").status_code == 302

    # Alice crée un compte et une étagère ; Bob ne doit pas y accéder par l'URL (R1)
    client.post("/inscription", data={"identifiant": "alice", "email": "a@m.fr", "mot_de_passe": "motdepasse123"})
    client.post("/etageres", data={"nom": "Haut", "capacite": "10"})
    id_etagere = application.db.utilisateurs[1].cave.etageres[0].id_etagere
    assert client.get(f"/etageres/{id_etagere}").status_code == 200

    bob = application.app.test_client()
    bob.post("/inscription", data={"identifiant": "bob", "email": "b@m.fr", "mot_de_passe": "azertyuiop"})
    assert bob.get(f"/etageres/{id_etagere}").status_code == 404
    assert bob.post(f"/etageres/{id_etagere}/supprimer").status_code == 404
