# Type de probleme: CARP
Trouver la route le cycle le plus court qui couvre l'entierete des arretes d'un graph mixte (arretes dirigees ou non dirigees) avec plusieurs objets.
Carp multi vehicule
Chaque deneigeuse part du depot et revient au depot
L'ensemble des tournees des deneigeuses doit couvrir toutes les routes de la zone

Minimiser le cout

# Donnees 
- Nombre de deneigeuses: ?
- Cout journalier fixe d'une deneigeuse : 500$ / jour 
- Cout kilometrique d'une deneigeuse : 1.1$ / km
- Cout horaire sur les 8 premieres heures : 1.1$ / h
- Cout horaire au dela des 8 premieres heures : 1.6$ / h
- Vitesse moyenne : 10 km / h

- Graph du secteur

# Fonction objectif
Minimiser le cout
Cout = Somme(i, cout_i) ; pour chaque deneigeuse i 
cout_i = jours_i * 500 + km_i * 1.1 + heures_norm_i * 1.1 + heures_sup_i * 1.6 ; le cout total d'une deneigeuse

# Contraintes

## Deneiger tout le perimetre etudié

## Contraintes logiques
- heures_norm_i <= 8 ; au dela de 8 heures = heures sup
## Contraintes liantes
- (heures_norm_i + heures_sup_i) / 24 = jours_i ; jours coherent avec heures
- (heures_norm_i + heures_sup_i) * 10 = km_i ; distance coherente avec heures (10km/h)

Questions :
Est ce que les scenarios proposes ont un rapport avec la solution (est ce qu'il faut integrer les priorites dans les contraintes)
Est ce que le mieux n'est pas de minimiser le temps dans tous les cas ? etant donne que le temps est le seule variable du cout qu'on peut changer
-- Sauf que plusieurs deneigeuses donc contrainte horaire fait qu'il est mieux d'utiliser une deneigeuse pour seulement 8h
-- Peut etre utiliser un nombre d'heures maximum par deneigeuse
