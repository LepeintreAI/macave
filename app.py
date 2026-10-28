# =====================================================================
#  APP.PY : l'application web MaCave (Flask)
# =====================================================================
# Rôle de ce fichier : recevoir les demandes du navigateur (les "routes"),
# appeler la bonne méthode de Database, puis afficher une page HTML.
# Il ne contient AUCUNE règle métier : les règles sont dans macave.py.
# =====================================================================

import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from database import Database
from macave import TYPES_VIN

app = Flask(__name__)

# Clé secrète : sert à signer la session (le "cookie" qui retient qui est connecté).
# Elle ne doit pas être écrite dans le code mis sur Git (§8 : pas de secrets) :
# on la lit dans une variable d'environnement, avec une valeur de secours pour le TP.
app.secret_key = os.environ.get("MACAVE_SECRET", "cle-de-developpement-a-changer")

db = Database("macave.db")      # charge toutes les données au démarrage

# Photos d'étiquettes : rangées dans static/photos, 2 Mo maximum par envoi
DOSSIER_PHOTOS = os.path.join(app.root_path, "static", "photos")
EXTENSIONS_PHOTO = (".jpg", ".jpeg", ".png", ".webp")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024     # au-delà, Flask refuse l'envoi (erreur 413)


# ---------------------------------------------------------------------
#  Outil : qui est connecté ?
# ---------------------------------------------------------------------
def utilisateur_connecte():
    # La session ne retient que l'id de l'utilisateur (ex. 1).
    # On retrouve l'objet complet grâce au dictionnaire de Database.
    id_u = session.get("id_utilisateur")        # None si personne n'est connecté
    if id_u is None:
        return None
    return db.utilisateurs.get(id_u)            # .get -> None si l'id n'existe plus


def lire_entier(texte, nom_du_champ):
    # Les formulaires envoient toujours du TEXTE ("10"), il faut le convertir en nombre.
    # int("abc") planterait avec un message anglais : on le remplace par un message clair.
    try:
        return int(texte)
    except ValueError:
        raise ValueError(f"Le champ « {nom_du_champ} » doit être un nombre entier")


def trouver_etagere(u, id_etagere):
    # On cherche l'étagère UNIQUEMENT dans la cave de l'utilisateur connecté.
    # Si Bob tape l'adresse d'une étagère d'Alice, elle n'est pas trouvée -> erreur 404 (R1).
    for e in u.cave.etageres:
        if e.id_etagere == id_etagere:
            return e
    abort(404)


def lire_decimal(texte, nom_du_champ):
    # Comme lire_entier, mais pour un prix : accepte "12,50" (virgule française) et "12.50"
    try:
        return float(texte.replace(",", "."))
    except ValueError:
        raise ValueError(f"Le champ « {nom_du_champ} » doit être un nombre")


def trouver_bouteille(u, id_bouteille):
    # Même principe que trouver_etagere : uniquement dans SA cave (R1)
    for b in u.cave.bouteilles:
        if b.id_bouteille == id_bouteille:
            return b
    abort(404)


def trouver_vin(id_vin):
    # Le catalogue est partagé : tout utilisateur connecté peut voir n'importe quel vin
    vin = db.vins.get(id_vin)
    if vin is None:
        abort(404)
    return vin


def evaluation_de(b):
    # Retrouve l'évaluation liée à une bouteille archivée (elle est rangée dans le vin)
    for ev in b.vin.evaluations:
        if ev.bouteille is b: # celle qui concerne CETTE bouteille
            return ev
    return None


def enregistrer_photo(fichier):
    # Reçoit le fichier envoyé par le formulaire. Renvoie le nom sous lequel il est
    # enregistré, ou None si aucune photo n'a été choisie.
    if fichier is None or fichier.filename == "":
        return None
    extension = os.path.splitext(fichier.filename)[1].lower()       # ".JPG" -> ".jpg"
    if extension not in EXTENSIONS_PHOTO:
        raise ValueError("La photo doit être une image JPG, PNG ou WEBP")
    # On NE garde PAS le nom d'origine (il pourrait contenir "../" ou écraser un autre fichier) :
    # on génère un nom unique et aléatoire.
    nom = uuid.uuid4().hex + extension                             # ex. "3f9a...c2.jpg"
    fichier.save(os.path.join(DOSSIER_PHOTOS, nom))
    return nom


def trier(lignes, cle, ordre):
    # lignes : la liste à trier (des bouteilles ou des vins)
    # cle    : une FONCTION qui dit sur quoi comparer (ex. le prix d'une bouteille)
    # ordre  : "asc" (croissant) ou "desc" (décroissant)

    avec_valeur = [l for l in lignes if cle(l) is not None]
    # on garde les lignes qui ONT une valeur à comparer
    # (= for l in lignes: if cle(l) is not None: avec_valeur.append(l))

    sans_valeur = [l for l in lignes if cle(l) is None]
    # on met de côté celles qui n'en ont PAS (ex. un vin « Non évalué »)

    avec_valeur.sort(key=cle, reverse=(ordre == "desc"))
    # on trie celles qui ont une valeur :
    #   key=cle            -> compare ce que renvoie cle(l) pour chaque ligne
    #   reverse=True/False -> True si ordre vaut "desc" (du plus grand au plus petit)

    return avec_valeur + sans_valeur
    # on recolle : les triées d'abord, les « sans valeur » toujours à la fin


def filtrer(lignes, vin_de, recherche, type_vin):
    # lignes    : la liste à filtrer
    # vin_de    : une FONCTION qui donne le vin d'une ligne
    #             (stock : lambda b: b.vin   /   catalogue : lambda v: v)
    # recherche : le texte tapé, ex. "mont"
    # type_vin  : le type choisi, ex. "rouge" (ou "" = tous)

    recherche = recherche.strip().lower()   # "  MONT " -> "mont"
    resultat = []                           # la liste des lignes qu'on garde

    for l in lignes:                        # pour chaque ligne...
        v = vin_de(l)                       # ...on récupère son vin

        if recherche and recherche not in v.nom.lower() and recherche not in v.domaine.lower():
            continue
        # S'il y a une recherche ET qu'elle n'est ni dans le nom ni dans le domaine,
        # on SAUTE cette ligne (continue = passer directement au tour suivant).
        # "in" vérifie si un texte est contenu dans un autre : "mont" in "château montelena" -> True

        if type_vin and v.type_vin != type_vin:
            continue
        # S'il y a un type choisi ET que ce vin n'est pas de ce type, on le saute aussi.

        resultat.append(l)                  # la ligne a passé les 2 tests -> on la garde

    return resultat


# Pour chaque colonne triable : comment obtenir la valeur à comparer à partir d'un vin
CLES_VIN = {                                   # dictionnaire : nom de colonne -> fonction
    "domaine":   lambda v: v.domaine.lower(),  # pour trier par domaine : on compare le domaine en minuscules
    "nom":       lambda v: v.nom.lower(),      # idem pour le nom
    "type":      lambda v: v.type_vin,         # le type (déjà en minuscules)
    "millesime": lambda v: v.millesime,        # un nombre
    "region":    lambda v: v.region.lower(),
    "note":      lambda v: v.note_moyenne(),   # un nombre, ou None si « Non évalué »
}


# ---------------------------------------------------------------------
#  Accueil : on envoie vers le tableau de bord ou vers la connexion
# ---------------------------------------------------------------------
@app.route("/")                                   # cette fonction répond à l'adresse "/"
def accueil():
    if utilisateur_connecte():                    # quelqu'un est connecté ? (objet -> vrai, None -> faux)
        return redirect(url_for("tableau_de_bord"))   # oui -> on l'envoie au tableau de bord
    return redirect(url_for("connexion"))         # non -> vers la page de connexion


# ---------------------------------------------------------------------
#  Inscription
# ---------------------------------------------------------------------
@app.route("/inscription", methods=["GET", "POST"])   # accepte l'affichage (GET) ET l'envoi (POST)
def inscription():
    if request.method == "POST":                      # l'utilisateur a cliqué sur « Créer mon compte »
        try:                                          # on essaie...
            u = db.creer_utilisateur(request.form["identifiant"],   # ce qu'il a tapé dans le champ name="identifiant"
                                     request.form["email"],
                                     request.form["mot_de_passe"])
        except ValueError as erreur:                  # ...si une règle refuse (identifiant pris, email sans @...)
            flash(str(erreur), "erreur")              # on prépare le message en rouge
            return render_template("inscription.html")   # et on réaffiche le formulaire
        session["id_utilisateur"] = u.id_utilisateur  # réussi : on retient son id -> il est connecté
        flash("Compte créé, bienvenue !", "succes")   # message vert
        return redirect(url_for("tableau_de_bord"))   # on l'envoie au tableau de bord

    return render_template("inscription.html")        # GET (simple visite) : formulaire vide


# ---------------------------------------------------------------------
#  Connexion
# ---------------------------------------------------------------------
@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    if request.method == "POST":                      # formulaire envoyé
        u = db.connecter(request.form["identifiant"], request.form["mot_de_passe"])
        # -> l'objet utilisateur si tout est bon, sinon None
        if u is None:                                 # identifiant ou mot de passe faux
            flash("Identifiant ou mot de passe incorrect", "erreur")   # message vague exprès (sécurité)
            return render_template("connexion.html")
        session["id_utilisateur"] = u.id_utilisateur  # on retient qui est connecté
        return redirect(url_for("tableau_de_bord"))

    return render_template("connexion.html")          # GET : formulaire vide


# ---------------------------------------------------------------------
#  Déconnexion
# ---------------------------------------------------------------------
@app.route("/deconnexion")                    # pas de methods -> GET seulement (un simple lien)
def deconnexion():
    session.clear()                           # on vide la session : plus personne n'est connecté
    flash("Vous êtes déconnecté.", "succes")
    return redirect(url_for("connexion"))


# ---------------------------------------------------------------------
#  Tableau de bord (§5.2) — page protégée
# ---------------------------------------------------------------------
@app.route("/tableau-de-bord")
def tableau_de_bord():
    u = utilisateur_connecte()                # qui est connecté ?
    if u is None:                             # personne -> accès refusé (contrôle côté serveur)
        flash("Veuillez vous connecter.", "erreur")
        return redirect(url_for("connexion"))

    cave = u.cave                             # SA cave, et pas une autre (R1)
    return render_template("tableau_de_bord.html",      # on affiche la page en lui donnant :
                           utilisateur=u,                         # l'utilisateur (pour son nom)
                           nb_bouteilles=len(cave.bouteilles_en_stock()),   # nb de bouteilles en stock
                           nb_references=cave.nb_references(),    # nb de vins différents
                           nb_etageres=cave.nb_etageres(),
                           occupation=cave.occupation_globale(),  # None si aucune étagère
                           valeur=cave.valeur_stock())
    # Dans le HTML, {{ nb_bouteilles }} sera remplacé par la valeur calculée ici


# ---------------------------------------------------------------------
#  Étagères : liste + création (§3.2)
# ---------------------------------------------------------------------
@app.route("/etageres", methods=["GET", "POST"])
def etageres():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))

    if request.method == "POST":                      # formulaire « Nouvelle étagère »
        try:
            capacite = lire_entier(request.form["capacite"], "capacité")   # texte "10" -> nombre 10
            e = db.creer_etagere(u, request.form["nom"], capacite)
            flash(f"Étagère « {e.nom} » créée.", "succes")
        except ValueError as erreur:                  # nom en double (R2), capacité <= 0...
            flash(str(erreur), "erreur")
        return redirect(url_for("etageres"))          # on réaffiche la liste à jour

    return render_template("etageres.html", etageres=u.cave.etageres)


# ---------------------------------------------------------------------
#  Une étagère : son contenu (§3.2)
# ---------------------------------------------------------------------
@app.route("/etageres/<int:id_etagere>")
def etagere(id_etagere):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    e = trouver_etagere(u, id_etagere)                # 404 si ce n'est pas la sienne
    return render_template("etagere.html", etagere=e)


# ---------------------------------------------------------------------
#  Modifier la capacité d'une étagère (R4)
# ---------------------------------------------------------------------
@app.route("/etageres/<int:id_etagere>/capacite", methods=["POST"])
def modifier_capacite(id_etagere):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    e = trouver_etagere(u, id_etagere)
    try:
        capacite = lire_entier(request.form["capacite"], "capacité")
        db.modifier_capacite(u, e, capacite)             # refuse si < nombre de bouteilles (R4)
        flash("Capacité modifiée.", "succes")
    except ValueError as erreur:                      # capacité < occupation (R4)...
        flash(str(erreur), "erreur")
    return redirect(url_for("etagere", id_etagere=id_etagere))
   # dans tous les cas, on revient sur la page de l'étagère.
    # url_for avec un paramètre fabrique l'adresse /etageres/3

# ---------------------------------------------------------------------
#  Supprimer une étagère (R5)
# ---------------------------------------------------------------------
@app.route("/etageres/<int:id_etagere>/supprimer", methods=["POST"])
def supprimer_etagere(id_etagere):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    e = trouver_etagere(u, id_etagere)
    try:
        db.supprimer_etagere(u, e)     # refuse si elle n'est pas vide (R5)
        flash(f"Étagère « {e.nom} » supprimée.", "succes")
        return redirect(url_for("etageres"))    # réussi -> retour à la LISTE (elle n'existe plus)
    except ValueError as erreur:                      # étagère non vide (R5)
        flash(str(erreur), "erreur")
        return redirect(url_for("etagere", id_etagere=id_etagere))


# ---------------------------------------------------------------------
#  Ajouter des bouteilles : choisir un vin existant OU en créer un (§4.2)
# ---------------------------------------------------------------------
@app.route("/bouteilles/ajouter", methods=["GET", "POST"])
def ajouter_bouteilles():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))

    if request.method == "POST":
        f = request.form                                  # raccourci : f["prix"] au lieu de request.form["prix"]
        try:
            # --- 1. LE VIN ---
            if f["id_vin"]:                               # un vin a été choisi dans la liste
                                                          # ("" = « Nouveau vin » -> considéré comme faux)
                vin = trouver_vin(int(f["id_vin"]))       # "7" -> 7 -> l'objet vin n°7
            else:                                         # pas de choix -> nouveau vin décrit
                if not (f["domaine"].strip() and f["nom"].strip() and f["region"].strip()):
                    # si au moins UN des 3 champs est vide...
                    raise ValueError("Choisissez un vin du catalogue, ou remplissez domaine, nom et région")
                    # ...on lève nous-mêmes une erreur (attrapée par le except plus bas)
                photo = enregistrer_photo(request.files.get("photo"))
                # les FICHIERS arrivent dans request.files (pas request.form) ; None si pas de photo
                vin = db.trouver_ou_creer_vin(f["domaine"], f["nom"], f["type_vin"],
                                              lire_entier(f["millesime"], "millésime"),
                                              f["region"], f["description"], photo)
                # -> réutilise le vin s'il existe déjà, sinon le crée

            # --- 2. LES BOUTEILLES ---
            etagere = trouver_etagere(u, int(f["id_etagere"]))    # l'étagère choisie, dans SA cave
            quantite = lire_entier(f["quantite"], "quantité")      # "3" -> 3
            prix = lire_decimal(f["prix"], "prix d'achat")         # "12,50" -> 12.5
            db.ajouter_bouteilles(u, vin, etagere, quantite, prix) # place vérifiée, tout ou rien
            flash(f"{quantite} bouteille(s) de « {vin.nom} » ajoutée(s) sur « {etagere.nom} ».", "succes")
            return redirect(url_for("etagere", id_etagere=etagere.id_etagere))   # on montre l'étagère
        except ValueError as erreur:
            flash(str(erreur), "erreur")
            # PAS de return ici : on descend plus bas pour réafficher le formulaire

    if not u.cave.etageres:                               # liste vide = aucune étagère
        flash("Créez d'abord une étagère.", "erreur")
        return redirect(url_for("etageres"))

    vins = sorted(db.vins.values(), key=lambda v: (v.domaine.lower(), v.nom.lower()))
    # tous les vins du catalogue, triés par domaine puis par nom (pour la liste déroulante)
    # sorted renvoie une NOUVELLE liste triée

    return render_template("ajouter_bouteilles.html", vins=vins, etageres=u.cave.etageres,
                           types=TYPES_VIN, formulaire=request.form)
    # formulaire=request.form : après une erreur, on remet ce que l'utilisateur avait tapé

# ---------------------------------------------------------------------
#  Une bouteille : toutes ses actions sur une page
# ---------------------------------------------------------------------
@app.route("/bouteilles/<int:id_bouteille>")
def bouteille(id_bouteille):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    b = trouver_bouteille(u, id_bouteille)
    autres_etageres = [e for e in u.cave.etageres if e is not b.etagere]   # destinations possibles
    # toutes ses étagères SAUF celle où est déjà la bouteille -> destinations possibles
    return render_template("bouteille.html", b=b, autres_etageres=autres_etageres,
                           evaluation=evaluation_de(b))   # sa note si elle est archivée

@app.route("/bouteilles/<int:id_bouteille>/deplacer", methods=["POST"])
def deplacer_bouteille(id_bouteille):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    b = trouver_bouteille(u, id_bouteille)
    try:
        destination = trouver_etagere(u, int(request.form["id_etagere"]))
        db.deplacer_bouteille(u, b, destination)              # R7 : place vérifiée
        flash(f"Bouteille déplacée sur « {destination.nom} ».", "succes")
    except ValueError as erreur:
        flash(str(erreur), "erreur")
    return redirect(url_for("bouteille", id_bouteille=id_bouteille))


@app.route("/bouteilles/<int:id_bouteille>/prix", methods=["POST"])
def modifier_prix(id_bouteille):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    b = trouver_bouteille(u, id_bouteille)
    try:
        db.modifier_bouteille(u, b, lire_decimal(request.form["prix"], "prix d'achat"))
        flash("Prix modifié.", "succes")
    except ValueError as erreur:
        flash(str(erreur), "erreur")
    return redirect(url_for("bouteille", id_bouteille=id_bouteille))


@app.route("/bouteilles/<int:id_bouteille>/retirer", methods=["POST"])
def retirer_bouteille(id_bouteille):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    b = trouver_bouteille(u, id_bouteille)
    etagere = b.etagere                                        # on note avant le retrait
    try:                                                     # après le retrait, b.etagere vaudra None (ta classe le remet à None)
        db.retirer_bouteille(u, b)                             # refuse si elle est archivée (R8)
        flash("Bouteille retirée définitivement.", "succes")
        return redirect(url_for("etagere", id_etagere=etagere.id_etagere))
    except ValueError as erreur:
        flash(str(erreur), "erreur")
        return redirect(url_for("bouteille", id_bouteille=id_bouteille))


@app.route("/bouteilles/<int:id_bouteille>/archiver", methods=["POST"])
def archiver_bouteille(id_bouteille):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    b = trouver_bouteille(u, id_bouteille)
    try:
        note = lire_entier(request.form["note"], "note")
        db.archiver_bouteille(u, b, note, request.form["commentaire"])   # R8 + note 0..20
        flash("Bouteille archivée, merci pour votre évaluation !", "succes")
        return redirect(url_for("historique"))
    except ValueError as erreur:
        flash(str(erreur), "erreur")
        return redirect(url_for("bouteille", id_bouteille=id_bouteille))


# ---------------------------------------------------------------------
#  Fiche d'un vin : visible par tous les utilisateurs connectés (§4.4)
# ---------------------------------------------------------------------
@app.route("/vins/<int:id_vin>")
def vin(id_vin):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    v = trouver_vin(id_vin)
    # Les exemplaires de CE vin dans MA cave uniquement (les autres caves restent privées)
    mes_exemplaires = [b for b in u.cave.bouteilles_en_stock() if b.vin is v]
    return render_template("vin.html", vin=v, utilisateur=u, mes_exemplaires=mes_exemplaires)


# ---------------------------------------------------------------------
#  Modifier SON évaluation (R12)
# ---------------------------------------------------------------------
@app.route("/vins/<int:id_vin>/evaluations/<int:id_evaluation>", methods=["GET", "POST"])
def modifier_evaluation(id_vin, id_evaluation):
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    v = trouver_vin(id_vin)
    ev = next((e for e in v.evaluations if e.id_evaluation == id_evaluation), None)
    # next(...) = le PREMIER élément qui correspond, ou None si aucun
    if ev is None:
        abort(404)

    if request.method == "POST":
        try:
            note = lire_entier(request.form["note"], "note")
            db.modifier_evaluation(u, ev, note, request.form["commentaire"])
            flash("Évaluation modifiée.", "succes")
            return redirect(url_for("vin", id_vin=id_vin))
        except (ValueError, PermissionError) as erreur:       # PermissionError : pas l'auteur (R12)
            flash(str(erreur), "erreur")
            return redirect(url_for("vin", id_vin=id_vin))

    if ev.auteur is not u:                                     # on n'affiche même pas le formulaire
        flash("Vous ne pouvez modifier que vos propres évaluations", "erreur")
        return redirect(url_for("vin", id_vin=id_vin))
    return render_template("modifier_evaluation.html", vin=v, ev=ev)


# ---------------------------------------------------------------------
#  Historique des dégustations, trié par note (§5.1)
# ---------------------------------------------------------------------
@app.route("/historique")
def historique():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))
    ordre = request.args.get("ordre", "desc")                  # ?ordre=asc ou ?ordre=desc
    lignes = [(b, evaluation_de(b)) for b in u.cave.historique()]
    # une liste de COUPLES (bouteille, évaluation) : l[0] = bouteille, l[1] = évaluation
    # Convention (à citer dans le README) : une note absente est toujours rangée en dernier.
    avec_note = [l for l in lignes if l[1] is not None]
    sans_note = [l for l in lignes if l[1] is None]
    avec_note.sort(key=lambda l: l[1].note, reverse=(ordre == "desc"))   # tri sur la note
    lignes = avec_note + sans_note
    return render_template("historique.html", lignes=lignes, ordre=ordre)


# ---------------------------------------------------------------------
#  Mon stock : recherche, filtre et tri (§5.1)
# ---------------------------------------------------------------------
@app.route("/stock")
def stock():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))

    # Les choix de l'utilisateur arrivent dans l'adresse : /stock?q=chateau&type_vin=rouge&tri=prix&ordre=desc
    recherche = request.args.get("q", "")
    type_vin = request.args.get("type_vin", "")
    tri = request.args.get("tri", "domaine")
    ordre = request.args.get("ordre", "asc")

    # Une ligne = un exemplaire (une bouteille). Le tri par prix porte donc
    # sur le prix de chaque exemplaire (convention autorisée par le §5.1).
    bouteilles = filtrer(u.cave.bouteilles_en_stock(), lambda b: b.vin, recherche, type_vin)
    if tri == "prix":
        cle = lambda b: b.prix_achat
    else:
        cle_vin = CLES_VIN.get(tri, CLES_VIN["domaine"])
        cle = lambda b: cle_vin(b.vin)
    bouteilles = trier(bouteilles, cle, ordre)

    return render_template("stock.html", bouteilles=bouteilles, types=TYPES_VIN,
                           q=recherche, type_vin=type_vin, tri=tri, ordre=ordre)


# ---------------------------------------------------------------------
#  Catalogue partagé : tous les vins, visibles par tous les connectés (§3.3)
# ---------------------------------------------------------------------
@app.route("/catalogue")
def catalogue():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))

    recherche = request.args.get("q", "")
    type_vin = request.args.get("type_vin", "")
    tri = request.args.get("tri", "domaine")
    ordre = request.args.get("ordre", "asc")

    vins = filtrer(list(db.vins.values()), lambda v: v, recherche, type_vin)
    # TOUS les vins du catalogue ; ici chaque ligne EST déjà un vin -> lambda v: v
    vins = trier(vins, CLES_VIN.get(tri, CLES_VIN["domaine"]), ordre)
   # pas de cas « prix » : un vin n'a pas de prix (c'est chaque bouteille qui en a un)
    return render_template("catalogue.html", vins=vins, types=TYPES_VIN,
                           q=recherche, type_vin=type_vin, tri=tri, ordre=ordre)


# ---------------------------------------------------------------------
#  Mon profil : modifier son adresse électronique (§3.1)
# ---------------------------------------------------------------------
@app.route("/profil", methods=["GET", "POST"])
def profil():
    u = utilisateur_connecte()
    if u is None:
        return redirect(url_for("connexion"))

    if request.method == "POST":
        try:
            db.modifier_profil(u, request.form["email"])
            flash("Profil mis à jour.", "succes")
        except ValueError as erreur:
            flash(str(erreur), "erreur")
        return redirect(url_for("profil"))

    return render_template("profil.html", utilisateur=u)


# ---------------------------------------------------------------------
#  Photo trop lourde : message clair au lieu d'une page d'erreur brute
# ---------------------------------------------------------------------
@app.errorhandler(413)
def fichier_trop_gros(erreur):
    flash("La photo est trop lourde (2 Mo maximum).", "erreur")
    return redirect(url_for("ajouter_bouteilles"))


# ---------------------------------------------------------------------
#  Lancement
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # use_reloader=False : indispensable sous Spyder
    # threaded=False     : SQLite n'accepte qu'un seul "fil" par connexion
    app.run(debug=True, use_reloader=False, threaded=False)
