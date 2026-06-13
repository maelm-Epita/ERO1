# Installation et exécution du programme de démonstation


## 1. Créer un environnement virtuel

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 2. Installer les dépendances

Installer les bibliothèques :

```bash
pip install -r requirements.txt
```

---

## 3. Lancer le programme

Placez-vous dans le dossier contenant le fichier Python puis exécutez :

```bash
python main.py
```

---

## Résultats

À la fin de l'exécution, le programme :

* affiche les statistiques d'optimisation dans le terminal ;
* génère des cartes interactives HTML pour chaque scénario exécuté.

Exemples de fichiers générés :

```text
Verdun_A.html
Verdun_B.html
Verdun_C.html
```

Ouvrez simplement ces fichiers dans un navigateur Web pour visualiser les trajets des déneigeuses.

# Résultats par secteur

Vous trouverez les résultats pour chacun des secteurs dans le dossier `Parcours`

Chaque secteur possède un resultat par scénario sous forme de pages HTML, qu'il est possible d'ouvrir avec un navigateur web.

## Format du résultat

La page HTML affiche une carte du secteur avec des traits tracés representant les chemins parcourus par les déneigeuses.

Chaque déneigeuse est representée par une couleur différente.

Il est possible qu'une déneigeuse passe par une rue précedemment déneigée par une autre déneigeuse, dans ce cas là, le trait n'est pas re-tracé.

Le fichier HTML de resultat affiche également en bas a gauche de la page des statistiques sur le parcours :

- Nombre de déneigeuses
- Coût 
- Distance
- Durée

- Distance par camion
