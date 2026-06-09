# Type de probleme: CARP
Trouver la route le cycle le plus court qui couvre l'entierete des arretes d'un graph mixte (arretes dirigees ou non dirigees) avec plusieurs objets.
Carp multi vehicule
Chaque deneigeuse part du depot et revient au depot
L'ensemble des tournees des deneigeuses doit couvrir toutes les routes de la zone

Minimiser le cout et le temp

# Donnees 
- Nombre de deneigeuses: ?
- Cout journalier fixe d'une deneigeuse : 500$ / jour 
- Cout kilometrique d'une deneigeuse : 1.1$ / km
- Cout horaire sur les 8 premieres heures : 1.1$ / h
- Cout horaire au dela des 8 premieres heures : 1.6$ / h
- Vitesse moyenne : 10 km / h

- Graph du secteur

# Formalisation mathematique
Soit un graph G = (V, E) 
- V l'ensemble des sommets
- E l'ensemble des arretes
Chaque arrete (i, j) possede une distance d_i_j en km

Soit K l'ensemble des deneigeuses
Soit k une deneigeuse appartenenant a K

Soit t_i_j le temps necessaire pour parcourir l'arrete (i, j) :
t_i_j = d_i_j / 10

Soit T_k le temps total pour une deneigeuse k :
T_k = somme(t_i_j)

Temp pour une deneigeuse k :
- heures_norm_k = min(T_k, 8)
- heures_sup_k = max(0, T_k - 8)
- jours_k = T_k / 24

Cout pour une deneigeuse :
Soit d_k la distance totale parcourue
C_k = jours_k * 500 + d_k * 1.1 + heures_norm_k * 1.1 + heures_sup_k * 1.6

Cout total :
Cout = Somme(C_k) ; pour chaque k de K

Temps global du deneigement :
Temps = max(T_k) ; pour chaque k de K

# Fonction objectif
Optimisation multi-objectif : on minimise conjointement le cout et le temps global
On utilise la somme ponderee pour ramener les deux criteres a un seul score global a minimiser

Soient alpha et beta les coefficients de ponderation :
CT = ( alpha * Cout ) + ( beta * Temps )

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
