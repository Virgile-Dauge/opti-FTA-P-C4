# 🔌 Spécifications - Outil d'Optimisation TURPE C4

**Date** : 2025-10-01
**Version** : 1.0
**Statut** : En développement

---

## 📋 Contexte du projet

### Problématique métier
Déterminer la **puissance souscrite optimale** et la **formule tarifaire d'acheminement** (CU ou LU) qui minimise les coûts annuels d'acheminement électrique, en tenant compte :
- Des coûts fixes (proportionnels à la puissance souscrite)
- Des coûts de dépassement (pénalités horaires)

---

## 🎯 Objectif principal

**À partir d'une courbe de charge en CSV (format Enedis), calculer :**
1. Le couple optimal **(Puissance souscrite P, Formule Tarifaire d'Acheminement CU/LU)**
2. Le **gain annuel** par rapport à la situation actuelle du client
3. Un **bilan mensuel des dépassements** pour la puissance actuelle

---

## 📥 Données d'entrée

### 1. Courbe de charge (obligatoire)
- **Format** : CSV Enedis
- **Colonnes attendues** :
  - `Horodate` : YYYY-MM-DD HH:MM:SS
  - `Grandeur physique` : "PA" (Puissance Active)
  - `Valeur` : Puissance en Watts (W)
- **Période** : Minimum 1 an de données
- **Fréquence** : Pas de 5 minutes

### 2. Situation actuelle du client (paramètres)
- **P actuelle** : Puissance souscrite actuelle (kW)
- **FTA actuelle** : Formule Tarifaire d'Acheminement actuelle (CU ou LU)

### 3. Paramètres TURPE (ajustables)
- **CG** : Composante de gestion annuelle (€) - *défaut : 217,80*
- **CC** : Composante de comptage annuelle (€) - *défaut : 283,27*
- **CS_CU** : Composante de soutirage CU (€/kW/an) - *défaut : 17,61*
- **CS_LU** : Composante de soutirage LU (€/kW/an) - *défaut : 30,16*
- **CMDPS** : Coût mensuel dépassement (€/h) - *défaut : 12,41*
- **CTA** : Contribution Tarifaire d'Acheminement - *défaut : 1,2193*

### 4. Plage de simulation (ajustable)
- **P min** : Puissance minimale à tester (kW) - *défaut : 36*
- **P max** : Puissance maximale à tester (kW) - *défaut : 66*

---

## 📤 Résultats attendus

### 1. Résultats principaux

#### Situation optimale
- **P optimale CU** : Puissance souscrite optimale en option CU (kW)
- **Coût annuel CU** : Coût total annuel en option CU (€/an)
- **P optimale LU** : Puissance souscrite optimale en option LU (kW)
- **Coût annuel LU** : Coût total annuel en option LU (€/an)

#### Recommandation
- **Option recommandée** : CU ou LU
- **P recommandée** : Puissance souscrite recommandée (kW)
- **Coût optimal** : Coût annuel minimal (€/an)

#### Comparaison avec la situation actuelle
- **Coût actuel** : Coût annuel avec P actuelle et FTA actuelle (€/an)
- **Gain annuel** : Économie réalisable (€/an)
- **Pourcentage d'économie** : Gain relatif (%)

### 2. Visualisations

#### Graphique principal
- **Axes** :
  - X : Puissance souscrite (kW)
  - Y : Coût annuel (€/an)
- **Courbes** :
  - Total CU (bleu)
  - Total LU (orange)
  - Point actuel (marqueur rouge)
  - Point optimal (marqueur vert)

#### Bilan mensuel des dépassements
Tableau mensuel pour **P actuelle** :
- **Mois**
- **Heures de dépassement**
- **Coût des dépassements** (€)

### 3. Exports

#### Fichier Excel `Simulation_TURPE.xlsx`
Colonnes :
- `PS` : Puissance souscrite testée (kW)
- `CU fixe` : Coût fixe annuel CU (€)
- `LU fixe` : Coût fixe annuel LU (€)
- `Dépassement` : Coût dépassements annuels (€)
- `Total CU` : Coût total CU (€)
- `Total LU` : Coût total LU (€)

---

## ✅ Validations et contraintes

### 1. Validation des données d'entrée

#### Vérifications obligatoires
- ✅ Présence des colonnes requises (`Horodate`, `Grandeur physique`, `Valeur`)
- ✅ Présence de données PA (Puissance Active)
- ✅ Format de date valide
- ✅ Valeurs numériques cohérentes (pas de NaN, pas de valeurs négatives)

#### Filtrage temporel
- ✅ **Ne conserver que la dernière année de données** (365 jours)
  - Si > 1 an de données : filtrer pour garder les 365 derniers jours
  - Si < 1 an de données : afficher un warning mais autoriser le calcul

#### Détection de trous de données
- ✅ Identifier les périodes manquantes (> 1h sans mesure)
- ✅ Afficher un avertissement si trous significatifs (> 1% de la période)
- ✅ Calculer le **taux de complétude** des données (%) :
  ```
  Taux complétude = (Nombre mesures réelles / Nombre mesures attendues) × 100
  ```
- ⚠️ **Warning si < 95%** : "Attention : données incomplètes, résultats potentiellement biaisés"
- ❌ **Erreur si < 80%** : "Données insuffisantes pour une analyse fiable"

### 2. Calcul des dépassements

#### Méthode actuelle
- Agrégation horaire (moyenne sur 1h)
- Comparaison avec P souscrite
- Comptage des heures de dépassement

#### ⚠️ Validation nécessaire
- **Objectif** : Être au plus proche du calcul Enedis
- **Action** : Comparer avec un cas client réel ayant eu beaucoup de dépassements
- **Critère** : Écart < 5% avec la facture Enedis

---

## ❓ Questions ouvertes

### 1. 🚨 Problème identifié : Moyennage 5 minutes vs Pmax réels

#### Contexte
> "On vient de réaliser qu'on utilisait le script et ça pouvait arriver de conseiller un passage de C4 à C5, mais **le moyennage sur 5 minutes empêche de voir les Pmax** qui sont parfois fréquemment au-dessus de 36 ! Et donc pas du tout judicieux de passer en C5 !"

#### Analyse
- Les données Enedis C4 sont moyennées sur **10 minutes**
- Les **Pmax facturés** peuvent être calculés sur des pas de temps plus courts
- Risque : recommander un passage C4 → C5 alors que les Pmax dépassent 36 kW

#### Questions
1. **Faut-il intégrer des données SGE supplémentaires ?**
   - Index quotidien
   - Mesure facturante
   - Pmax réels

2. **Si oui, quel format et quelle source ?**
   - Fichier séparé à uploader ?
   - Intégration dans le CSV Enedis ?

3. **Comment calculer les Pmax ?**
   - Sur quel pas de temps ? (1 min, 5 min ?)
   - Quelle méthode d'agrégation ?

#### Action requise
- **Clarifier avec le client** le besoin exact
- **Obtenir un exemple de données SGE** si nécessaire

### 2. 📊 Validation du calcul des dépassements

#### Action requise
- **Fournir un cas client réel** avec :
  - Courbe de charge complète (1 an)
  - Factures Enedis avec détail des dépassements
  - P souscrite et FTA
- **Comparer les résultats** de l'outil avec les factures Enedis
- **Ajuster l'algorithme** si nécessaire

---

## 🖥️ Format de livraison

### Solution technique : HTML autonome interactif

#### Pourquoi pas un .exe Windows ?
- ❌ Difficile à tester sans Windows
- ❌ Problèmes de compatibilité potentiels
- ❌ Difficile à maintenir et mettre à jour

#### Avantages du HTML autonome
- ✅ Double-clic → s'ouvre dans le navigateur
- ✅ Pas de souci de compatibilité OS
- ✅ Facile à partager (fichier unique ou dossier Dropbox)
- ✅ Possibilité de déployer sur un site web plus tard
- ✅ Permet de **fédérer plusieurs outils** sur un même site

#### Technologie
- **Base** : Notebook Marimo converti en HTML statique
- **Alternative** : Application Streamlit déployable

### Interface utilisateur

#### Zones principales
1. **Upload** : Zone drag & drop pour le CSV
2. **Paramètres** : Inputs pour :
   - Situation actuelle (P, FTA)
   - Paramètres TURPE (avec valeurs par défaut)
   - Plage de simulation (P min, P max)
3. **Résultats** : Affichage des résultats optimaux + comparaison
4. **Visualisations** : Graphique interactif + tableau mensuel
5. **Export** : Bouton de téléchargement Excel

---

## 🚀 Prochaines étapes

### Phase 1 : Validation des spécifications ✅
- [x] Synthèse des besoins
- [ ] **Validation client** de ce document

### Phase 2 : Données de test (En attente client)
- [ ] **Obtenir 1-2 exemples de CSV réels** (format Enedis, 1 an de données)
- [ ] **Obtenir un cas client avec dépassements** pour validation
- [ ] **Clarifier le besoin de données SGE** (Pmax réels)

### Phase 3 : Développement (0.5 jour estimé)
- [ ] Implémenter le filtrage dernière année
- [ ] Implémenter la détection de trous de données
- [ ] Ajouter le calcul de la situation actuelle
- [ ] Ajouter le bilan mensuel des dépassements
- [ ] Créer l'interface HTML autonome
- [ ] Tester avec les données réelles

### Phase 4 : Validation et ajustements
- [ ] Comparer résultats vs factures Enedis
- [ ] Ajuster l'algorithme si nécessaire
- [ ] Tests utilisateur

### Phase 5 : Déploiement
- [ ] Livraison HTML autonome
- [ ] Documentation utilisateur
- [ ] Optionnel : Déploiement sur site web

---

## 📝 Notes et remarques

### Différences C4 vs C2
> "J'ai quelque chose de similaire pour les C2 mais il faut que je nettoie et que je commente le code pour que ça soit réutilisable"

**Question** : Faut-il prévoir une version C2 également ?
- Si oui, quelles sont les différences métier ?
- Peut-on mutualiser le code ?

### Extension future : Fédération d'outils
L'architecture HTML/web permet de centraliser plusieurs outils d'optimisation :
- Optimisation C4 (ce projet)
- Optimisation C2 (à nettoyer)
- Autres outils d'analyse énergétique

**Vision** : Plateforme web unifiée plutôt que des .exe dispersés

---

## 📞 Contact

**Développeur** : Virgile
**Client** : Marion + équipe
**Origine** : Hamza (script initial)
