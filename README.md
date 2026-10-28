# MaCave — gestion collaborative d'une cave à vin

Mini-projet ETRS711 (Master TRI). Application web Python / Flask / SQLite permettant à
plusieurs utilisateurs de gérer leur cave privée (étagères, bouteilles), d'archiver leurs
dégustations avec une note et de partager les évaluations avec la communauté.

> **Auteur :** Franck GEISTLICH

---

## 1. Installation

Prérequis : Python 3.10 ou plus récent.

```bash
python -m venv venv                 # (facultatif) environnement virtuel
venv\Scripts\activate               # Windows    |  source venv/bin/activate  (Linux / macOS)
pip install -r requirements.txt
```

## 2. Initialiser la base (jeu de démonstration)

```bash
python demo.py
```

Cette commande **efface** `macave.db` s'il existe, puis crée :

| Compte | Mot de passe | Contenu |
|---|---|---|
| `alice` | `alice2026` | 3 étagères, 4 vins, 11 bouteilles en stock (dont 4 Montelena identiques), 1 dégustation |
| `bob` | `bob20262026` | 1 étagère, 2 vins, 3 bouteilles en stock, 2 dégustations |

Le vin *Château Montelena 1967* est noté 16 (alice), 12 et 17 (bob) : moyenne communautaire **15/20**.

Sans `demo.py`, une base vide est créée automatiquement au premier lancement.

## 3. Lancer l'application

```bash
python app.py
```

Puis ouvrir <http://127.0.0.1:5000>. Sous Spyder, lancer `app.py` directement
(le rechargement automatique est désactivé pour cette raison).

La clé de session est lue dans la variable d'environnement `MACAVE_SECRET`.
Une valeur de secours est utilisée en développement ; **en production, définir `MACAVE_SECRET`**.

## 4. Lancer les tests

```bash
pytest
```

11 tests automatisés (`tests/test_macave.py`) :

| Test | Règle vérifiée |
|---|---|
| dépassement de capacité | R3 + atomicité : 6 bouteilles sur 5/10 refusées, aucun ajout partiel |
| retrait d'un exemplaire | R6 : 5 → 4, pas d'historique |
| déplacement | occupations mises à jour, R7 : destination pleine refusée |
| archivage | 4 en stock / 1 en historique, place libérée, R8, R11 |
| moyenne communautaire | 16, 12, 17 → 15 ; « Non évalué » sans note ; modification répercutée |
| données invalides | capacité, quantité, prix, note, type de vin |
| étagère non vide | R4, R5 |
| doublons de vin | casse et espaces ignorés |
| contrôle d'accès (objets) | R1, R12 |
| persistance | données identiques après fermeture / réouverture de la base |
| pages web protégées | redirection si non connecté, 404 sur l'étagère d'un autre utilisateur |

---

## 5. Organisation du code

```
macave_web/
├── macave.py          couche métier : classes et règles de gestion (aucun SQL)
├── database.py        couche persistance : tables SQLite, sauvegarde, chargement, transactions
├── app.py             couche web : routes Flask, sessions, validation des formulaires
├── demo.py            jeu de démonstration
├── templates/         pages HTML (Jinja2) ; base.html = menu et messages communs
├── static/photos/     photos d'étiquettes envoyées
├── tests/             tests pytest
└── docs/uml/          diagrammes UML (sources draw.io + PNG)
```

Chaque action suit le même trajet :
**formulaire HTML → route `app.py` → méthode de `Database` → méthode métier de `macave.py`
(vérification des règles) → écriture SQL → message + page suivante.**

## 6. Choix de conception

- **Vin ≠ Bouteille.** `Vin` est la référence partagée du catalogue ; `Bouteille` est un exemplaire
  physique privé, avec son propre prix et sa propre date. 5 bouteilles identiques = 5 objets
  `Bouteille` liés à un seul `Vin`.
- **`Cave` orchestre** toutes les opérations sur les étagères et les bouteilles ; chaque classe ne
  modifie que ses propres données.
- **Règles dans les classes, pas dans la base ni dans Flask.** Les classes sont testables sans base
  ni serveur web (§6.2). La base ajoute des contraintes de sécurité (`UNIQUE`, `CHECK`, clés étrangères).
- **Vérifier avant de modifier.** Chaque méthode fait toutes ses vérifications avant le moindre
  changement : une opération refusée ne laisse aucune modification partielle.
- **Une seule liste de bouteilles par cave** (stock + historique), séparées par le statut
  (`en stock` / `archivée`) : même forme que la table `bouteille`, aucune bouteille ne peut être
  « à deux endroits ».
- **Attributs dérivés calculés, jamais stockés** : occupation, moyenne, indicateurs du tableau de bord.
- **Une cave par utilisateur**, avec le même identifiant : pas de table `cave` séparée.

## 7. Modèle relationnel

```
utilisateur (id PK, identifiant UNIQUE, email, mot_de_passe_hash)
etagere     (id PK, id_utilisateur FK→utilisateur, nom, capacite CHECK > 0)
vin         (id PK, domaine, nom, type_vin, millesime, region, description, photo)
bouteille   (id PK, id_utilisateur FK→utilisateur, id_vin FK→vin, id_etagere FK→etagere NULL si archivée,
             prix_achat CHECK > 0, date_ajout, statut, date_sortie)
evaluation  (id PK, id_auteur FK→utilisateur, id_vin FK→vin, id_bouteille FK→bouteille,
             note CHECK 0..20, commentaire, date)
```

- Les clés étrangères sont activées (`PRAGMA foreign_keys = ON`).
- **Transactions** : l'ajout de plusieurs bouteilles et l'archivage (mise à jour de la bouteille +
  création de l'évaluation) sont écrits dans une seule transaction (`with conn:`) : tout est validé
  ou tout est annulé.
- Au démarrage, `Database.charger()` reconstruit tous les objets à partir des tables.

## 8. Conventions retenues

- **Doublons de vins** : l'identité d'un vin repose sur (domaine, nom, type, millésime, région),
  comparés **sans tenir compte de la casse ni des espaces en trop** (`Vin.cle_identite()`).
  Un vin déjà présent est réutilisé au lieu d'être recréé.
- **Noms d'étagères** : uniques dans une cave, même comparaison (casse et espaces ignorés).
- **Valeurs absentes dans les tris** : un vin « Non évalué » est **toujours placé en dernier**,
  quel que soit le sens du tri.
- **Tri par prix** : le stock affiche une ligne par exemplaire ; le tri porte sur le prix de chaque bouteille.
- **Moyenne** : moyenne simple de toutes les évaluations (chaque dégustation a le même poids, R10) ;
  sans évaluation, affichage « Non évalué » (jamais 0).
- **Tableau de bord sans étagère** : occupation globale affichée « Aucune étagère » (pas de division par zéro).
- **Confidentialité** : le catalogue et les évaluations sont visibles par tous les utilisateurs
  connectés ; le stock, les étagères, les prix et l'historique restent privés. Une étagère ou une
  bouteille d'un autre utilisateur répond « 404 introuvable ».

## 9. Sécurité

- Mots de passe hachés avec `werkzeug.security` (scrypt, avec sel), jamais stockés en clair.
- Contrôles d'accès faits côté serveur dans chaque route, y compris en cas d'accès direct à une URL.
- Requêtes SQL paramétrées (`?`) : pas d'injection SQL.
- Photos : extensions JPG/PNG/WEBP uniquement, 2 Mo maximum, renommées avec un nom aléatoire.
- Message de connexion volontairement vague (« identifiant ou mot de passe incorrect »).

## 10. Limites connues

- Serveur de développement Flask, prévu pour une utilisation locale (pas de déploiement).
- Une seule requête traitée à la fois (`threaded=False`), car la connexion SQLite est partagée.
- Si un ajout échoue après l'envoi d'une photo (par exemple étagère pleine), le fichier reste dans
  `static/photos` sans être utilisé.
- La photo d'un vin ne peut être ajoutée qu'à sa création.
- Les règles d'unicité (noms d'étagères, vins) sont garanties par les classes métier ; la base ne
  vérifie elle-même que l'unicité de l'identifiant.
- Pas de suppression de compte ni de suppression d'un vin du catalogue.
