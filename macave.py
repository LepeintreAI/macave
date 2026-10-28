import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash

TYPES_VIN = ("rouge", "blanc", "rosé", "effervescent")   # les 4 types autorisés (§4.1)

# =====================================================================
#  UTILISATEUR
# =====================================================================


class Utilisateur:
    def __init__(self, id_utilisateur, identifiant, email, mot_de_passe):
        # --- Vérifications d'abord ---
        if identifiant.strip() == "":
            raise ValueError("L'identifiant est obligatoire")
        self.verifier_email(email)
        if len(mot_de_passe) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")

        # --- Affectations ensuite ---
        self.id_utilisateur = id_utilisateur
        self.identifiant = identifiant.strip()
        self.email = email.strip()
        # Jamais le mot de passe en clair (§3.1) : on stocke uniquement son hash
        # generate_password_hash ajoute un « sel » aléatoire : deux utilisateurs avec
        # le même mot de passe n'auront PAS le même hash (plus sûr que sha256 seul)
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)
        # Une cave par utilisateur, créée automatiquement.
        # self = cet utilisateur -> il devient le propriétaire de la cave
        self.cave = Cave(id_utilisateur, self)


    def verifier_email(self, email):
        # Vérification simple : un @ et pas vide
        if "@" not in email or email.strip() == "":
            raise ValueError("Adresse électronique invalide")


    def verifier_mot_de_passe(self, mdp):
        # On ne peut pas « déchiffrer » un hash : check_password_hash hashe le mot de
        # passe saisi avec le même sel, puis compare. Renvoie True ou False.
        return check_password_hash(self.mot_de_passe_hash, mdp)


    def modifier_profil(self, email):
        self.verifier_email(email)       # même règle qu'à la création
        self.email = email.strip()


    def possede(self, cave):
        # R1 : est-ce bien SA cave ? (is = le même objet, pas juste « pareil »)
        return cave is self.cave


    def __str__(self):
        return self.identifiant
      
    
# =====================================================================
#  Evaluation
# =====================================================================
class Evaluation:
    def __init__(self, id_evaluation, auteur, vin, bouteille, note, commentaire=None):
        # commentaire=None : valeur par défaut -> le commentaire est facultatif (§4.3)

        # --- Vérifications d'abord ---
        self.verifier_note(note)

        # --- Affectations ensuite ---
        self.id_evaluation = id_evaluation
        self.note = note
        self.commentaire = self.nettoyer_commentaire(commentaire)
        self.date = date.today()

        # R11 : chaque évaluation est liée à un auteur, un vin et une bouteille archivée
        self.auteur = auteur          # objet Utilisateur
        self.vin = vin                # objet Vin (c'est lui qui calcule la moyenne)
        self.bouteille = bouteille    # objet Bouteille (celle qui a été dégustée)


    def verifier_note(self, note):
        # La note doit être un entier compris entre 0 et 20 (§4.3)
        if not isinstance(note, int):
            raise ValueError("La note doit être un nombre entier")
        if note < 0 or note > 20:
            raise ValueError("La note doit être comprise entre 0 et 20")


    def nettoyer_commentaire(self, commentaire):
        # Un commentaire vide ou rempli d'espaces est considéré comme absent
        if commentaire is None or commentaire.strip() == "":
            return None
        return commentaire.strip()


    def modifier(self, utilisateur, note, commentaire=None):
        # R12 : seul l'auteur peut modifier son évaluation
        if utilisateur is not self.auteur:
            raise PermissionError("Vous ne pouvez modifier que vos propres évaluations")
        self.verifier_note(note)

        # Toutes les vérifications sont passées -> on modifie
        self.note = note
        self.commentaire = self.nettoyer_commentaire(commentaire)
        # Pas besoin de toucher au vin : note_moyenne() relit .note à chaque appel,
        # donc la moyenne est mise à jour automatiquement (§4.4)


    def __str__(self):
        texte = f"{self.note}/20"              # "16/20"
        if self.commentaire:                   # s'il y a un commentaire (pas None)...
            texte += f" — {self.commentaire}"  # ...on l'ajoute à la suite : "16/20 — Superbe"
        return texte                           # sans commentaire, ça reste "16/20"

# =====================================================================
#  Vin
# =====================================================================
class Vin:
    def __init__(self, id_vin, description, domaine, nom, type_vin, millesime, photo, region):
        # --- Vérification d'abord : le type doit être l'une des 4 valeurs du sujet ---
        type_vin = type_vin.strip().lower()          # "  Rouge " -> "rouge"
        if type_vin not in TYPES_VIN:
            raise ValueError(f"Type de vin invalide : choisir parmi {', '.join(TYPES_VIN)}")

        self.id_vin = id_vin
        self.description = description
        self.domaine = domaine
        self.nom = nom
        self.type_vin = type_vin
        self.millesime = millesime
        self.photo = photo
        self.region = region
        self.evaluations = []


    def ajouter_evaluation(self, evaluation):
        self.evaluations.append(evaluation)
    
    def note_moyenne(self):
        # R9 : seules les notes vraiment enregistrées comptent.
        # Pas d'évaluation -> None (l'interface affichera « Non évalué », pas 0)
        if len(self.evaluations) == 0:
            return None

        somme = 0
        for evaluation in self.evaluations:      # chaque élément est un objet Evaluation
            somme = somme + evaluation.note      # .note : le nombre (0 à 20) dans l'objet

        # R10 : chaque dégustation a le même poids -> moyenne simple
        return somme / len(self.evaluations)
        # Rien n'est stocké dans self : la moyenne est recalculée à chaque appel,
        # donc une note modifiée est prise en compte automatiquement.


    def cle_identite(self):
        # Renvoie les 5 champs qui définissent un vin (§4.1), nettoyés,
        # pour repérer les doublons malgré les espaces et les majuscules.

        def nettoyer(texte):
            # .split() découpe sur les espaces et supprime ceux qui sont en trop
            #   "  Château  Margaux " -> ["Château", "Margaux"]
            # " ".join(...) recolle avec un seul espace -> "Château Margaux"
            # .lower() met en minuscules               -> "château margaux"
            return " ".join(texte.split()).lower()

        return (
            nettoyer(self.domaine),
            nettoyer(self.nom),
            nettoyer(self.type_vin),
            self.millesime,              # c'est un nombre : rien à nettoyer
            nettoyer(self.region),
        )
        # Deux vins identiques donnent deux tuples égaux :
        # v1.cle_identite() == v2.cle_identite()  ->  True
    


# =====================================================================
#  Bouteille
# =====================================================================
class Bouteille:
    def __init__(self, id_bouteille, vin, prix_achat):
        if prix_achat <= 0:
            raise ValueError("Le prix doit être supérieur à 0")
        self.prix_achat = prix_achat
        self.id_bouteille = id_bouteille
        self.statut = "en stock"
        self.date_sortie = None
        self.date_ajout = date.today()
        self.vin = vin
        self.etagere = None

    
    def archiver(self):
        if self.statut == "archivée":
            raise ValueError("Cette bouteille est déjà archivée")
        self.statut = "archivée"
        self.date_sortie = date.today()
    
    def est_en_stock(self):
        # Renvoie directement le résultat de la comparaison (True ou False),
        # pas besoin de if/else
        return self.statut == "en stock"


    def modifier(self, prix):          # self en premier : la bouteille à modifier
        # Une bouteille archivée est dans l'historique : on ne la modifie plus
        if not self.est_en_stock():
            raise ValueError("Impossible de modifier une bouteille archivée")

        # Même règle que dans __init__ : prix strictement positif
        if prix <= 0:
            raise ValueError("Le prix d'achat doit être strictement positif")

        # On ne modifie qu'une fois que toutes les vérifications sont passées
        self.prix_achat = prix

# =====================================================================
#  étagère
# =====================================================================
class Etagere:
    def __init__(self, id_etagere, nom, capacite):
        if capacite <= 0:
            raise ValueError("La capacité doit être strictement positive")
        self.capacite = capacite
        self.id_etagere = id_etagere
        self.nom = nom
        self.bouteilles = []

    def occupation(self):
        # Attribut dérivé (/ dans le diagramme) : bouteilles actuellement sur l'étagère
        return len(self.bouteilles)


    def places_libres(self):
        # Ce qu'il reste : capacité - occupation
        return self.capacite - self.occupation()

    def peut_accueillir(self, n):
        # True s'il reste au moins n places -> utile pour l'ajout multiple (tout ou rien)
        return self.places_libres() >= n


    def ranger_bouteille(self, bouteille):
        # R3 : l'occupation ne dépasse jamais la capacité
        if not self.peut_accueillir(1):
            raise ValueError(f"L'étagère « {self.nom} » est pleine")
        self.bouteilles.append(bouteille)
        bouteille.etagere = self          # la bouteille sait maintenant où elle est


    def retirer_bouteille(self, bouteille):
        self.bouteilles.remove(bouteille)
        bouteille.etagere = None          # elle n'est plus sur aucune étagère


    def est_vide(self):
        # Utile pour R5 : on ne supprime pas une étagère non vide
        return len(self.bouteilles) == 0


    def taux_occupation(self):
        # Pas de division par zéro possible : capacite > 0 est garanti par __init__
        return len(self.bouteilles) / self.capacite


    def modifier_capacite(self, n):
        # Vérifications d'abord...
        if n <= 0:
            raise ValueError("La capacité doit être strictement positive")
        # R4 : on ne descend pas sous l'occupation actuelle
        if n < len(self.bouteilles):
            raise ValueError(
                f"Impossible : l'étagère contient déjà {len(self.bouteilles)} bouteilles"
            )
        # ... modification ensuite
        self.capacite = n

# =====================================================================
#  Cave
# =====================================================================
class Cave:
    def __init__(self, id_cave, proprietaire):
        self.id_cave = id_cave
        self.proprietaire = proprietaire
        self.etageres = []
        self.bouteilles = []
        self.compteur_bouteilles = 0
        self.compteur_evaluations = 0
    
    def verifier_etagere(self, etagere):
        if etagere not in self.etageres:
            raise PermissionError("Cette étagère n'appartient pas à votre cave")

    def verifier_bouteille(self, bouteille):
        if bouteille not in self.bouteilles:
            raise PermissionError("Cette bouteille n'appartient pas à votre cave")
    
    
    def nettoyer_nom(self, nom):
        # Même nettoyage que dans Vin : espaces en trop supprimés + minuscules C'est pour étagère
        # "  Haut  Gauche " -> "haut gauche"
        return " ".join(nom.split()).lower()


    def creer_etagere(self, nom, capacite):
        # --- Vérifications d'abord ---
        if self.nettoyer_nom(nom) == "":
            raise ValueError("Le nom de l'étagère est obligatoire")

        # R2 : noms uniques dans la cave (insensible aux espaces et à la casse)
        for e in self.etageres:
            if self.nettoyer_nom(e.nom) == self.nettoyer_nom(nom):
                raise ValueError(f"Une étagère « {e.nom} » existe déjà")

        # --- Création ensuite ---
        # Si la capacité est invalide, c'est Etagere.__init__ qui refuse
        etagere = Etagere(len(self.etageres) + 1, nom.strip(), capacite)
        self.etageres.append(etagere)
        return etagere          # on la renvoie pour pouvoir l'utiliser ensuite


    def supprimer_etagere(self, etagere):
        self.verifier_etagere(etagere)
        # R5 : une étagère non vide ne peut pas être supprimée
        if not etagere.est_vide():
            raise ValueError(
                f"L'étagère « {etagere.nom} » contient encore "
                f"{len(etagere.bouteilles)} bouteille(s) : déplacez-les ou retirez-les d'abord"
            )
        self.etageres.remove(etagere)


    def nb_etageres(self):
        return len(self.etageres)

    def ajouter_bouteilles(self, vin, etagere, quantite, prix):
        # --- Vérifications d'abord : AUCUNE bouteille créée avant la fin des tests ---
        self.verifier_etagere(etagere)
        if quantite <= 0:
            raise ValueError("La quantité doit être strictement positive")
        if prix <= 0:
            raise ValueError("Le prix d'achat doit être strictement positif")

        # R3 + atomicité : tout ou rien
        if not etagere.peut_accueillir(quantite):
            raise ValueError(
                f"Place insuffisante sur « {etagere.nom} » : "
                f"{etagere.places_libres()} place(s) libre(s) pour {quantite} bouteille(s)"
            )

        # --- Création ensuite : à ce stade, on SAIT que tout va passer ---
        nouvelles = []
        for i in range(quantite):                  # répète quantite fois
            self.compteur_bouteilles += 1          # id unique : 1, 2, 3...
            bouteille = Bouteille(self.compteur_bouteilles, vin, prix)
            etagere.ranger_bouteille(bouteille)    # met aussi bouteille.etagere à jour
            self.bouteilles.append(bouteille)      # la cave la détient
            nouvelles.append(bouteille)
        return nouvelles                           # 5 objets Bouteille, 1 seul Vin


    def deplacer_bouteille(self, bouteille, destination):
        # --- Vérifications ---
        self.verifier_bouteille(bouteille)
        self.verifier_etagere(destination)
        if not bouteille.est_en_stock():
            raise ValueError("Une bouteille archivée ne peut pas être déplacée")
        if bouteille.etagere is destination:
            raise ValueError("La bouteille est déjà sur cette étagère")
        # R7 : on vérifie la place AVANT de retirer la bouteille de son étagère
        if not destination.peut_accueillir(1):
            raise ValueError(f"L'étagère « {destination.nom} » est pleine")

        # --- Action : retirer de l'ancienne puis ranger sur la nouvelle ---
        bouteille.etagere.retirer_bouteille(bouteille)
        destination.ranger_bouteille(bouteille)


    def retirer_bouteille(self, bouteille):
        # Retrait définitif : la bouteille disparaît, sans historique (§4.3)
        self.verifier_bouteille(bouteille)
        # R8 : une bouteille archivée ne peut plus être retirée
        if not bouteille.est_en_stock():
            raise ValueError("Cette bouteille est archivée : elle ne peut pas être retirée")

        bouteille.etagere.retirer_bouteille(bouteille)   # libère la place
        self.bouteilles.remove(bouteille)                # disparaît de la cave
        # Le vin n'est pas touché : il reste dans le catalogue commun


    def archiver_bouteille(self, bouteille, note, commentaire=None):
        # --- Vérifications ---
        self.verifier_bouteille(bouteille)
        if not bouteille.est_en_stock():                 # R8
            raise ValueError("Cette bouteille est déjà archivée")

        # On crée l'évaluation EN PREMIER : si la note est invalide (ex. 25),
        # Evaluation lève l'erreur ici, et rien n'a encore été modifié
        evaluation = Evaluation(
            self.compteur_evaluations + 1,
            self.proprietaire,        # l'auteur (R11)
            bouteille.vin,            # le vin évalué (R11)
            bouteille,                # la bouteille dégustée (R11)
            note,
            commentaire,
        )

        # --- Action : tout est valide, on applique les 3 changements ---
        self.compteur_evaluations += 1
        bouteille.etagere.retirer_bouteille(bouteille)   # n'occupe plus de place
        bouteille.archiver()                             # statut + date de sortie
        bouteille.vin.ajouter_evaluation(evaluation)     # visible par la communauté
        # La bouteille RESTE dans self.bouteilles -> c'est l'historique
        return evaluation


    def bouteilles_en_stock(self):
        resultat = []
        for b in self.bouteilles:
            if b.est_en_stock():
                resultat.append(b)
        return resultat


    def historique(self):
        resultat = []
        for b in self.bouteilles:
            if not b.est_en_stock():
                resultat.append(b)
        return resultat


    def nb_references(self):
        # Un set ne garde qu'un exemplaire de chaque élément :
        # 5 bouteilles du même vin -> 1 seul vin dans le set
        vins = set()                           # un set vide : comme une liste, mais SANS doublons
        for b in self.bouteilles_en_stock():   # on parcourt chaque bouteille en stock
            vins.add(b.vin)                    # on ajoute SON vin (l'objet Vin, pas la bouteille)
                                               # si ce vin est déjà dans le set, add() ne fait rien
        return len(vins)                       # nombre de vins DIFFÉRENTS = nombre de références


    def occupation_globale(self):
        # Pas d'étagère -> None (Flask affichera « Aucune étagère »), pas de division par zéro
        if len(self.etageres) == 0:
            return None
        capacite_totale = 0
        for e in self.etageres:
            capacite_totale += e.capacite
        return len(self.bouteilles_en_stock()) / capacite_totale


    def valeur_stock(self):
        total = 0
        for b in self.bouteilles_en_stock():
            total += b.prix_achat
        return total