# 🔌 Optimisation TURPE C4 - Notebook Marimo Interactif

Application interactive pour déterminer la **puissance souscrite optimale** et la **formule tarifaire d'acheminement** (CU ou LU) qui minimise les coûts annuels d'acheminement électrique.

## 📋 Vue d'ensemble

Cet outil permet de :
- Analyser une courbe de charge électrique (format Enedis)
- Simuler les coûts TURPE (fixes + variables + dépassements) pour différentes puissances souscrites
- Comparer les options **CU** (Courte Utilisation) et **LU** (Longue Utilisation)
- Identifier la configuration optimale minimisant le coût annuel

### Objectif
Trouver le meilleur compromis entre :
- Les **coûts fixes** (qui augmentent avec la puissance souscrite)
- Les **coûts variables** (fonction de la consommation par cadran tarifaire)
- Les **coûts de dépassement** (qui diminuent avec une puissance souscrite plus élevée)

---

## 🚀 Installation

### Prérequis
- Python 3.10+
- [Marimo](https://marimo.io) - Framework de notebooks interactifs
- Polars - Manipulation rapide de DataFrames
- Altair - Visualisations interactives

### Installation des dépendances

```bash
pip install marimo polars altair
```

---

## 📊 Format du fichier d'entrée

Le notebook attend un fichier **CSV au format Enedis R63** avec les colonnes suivantes :

| Horodate | Grandeur physique | Valeur | Pas |
|----------|-------------------|--------|-----|
| 2024-01-01 00:00:00 | PA | 45000 | PT5M |
| 2024-01-01 00:05:00 | PA | 47500 | PT5M |

### Spécifications
- **Séparateur** : point-virgule (`;`)
- **Horodate** : Format `YYYY-MM-DD HH:MM:SS`
- **Grandeur physique** : `PA` (Puissance Active uniquement)
- **Valeur** : Puissance en Watts (W) - convertie automatiquement en kW
- **Pas** : Format ISO 8601 (ex: `PT5M` pour 5 minutes, `PT10M` pour 10 minutes)
- **Période** : Minimum 1 an de données pour une analyse représentative

---

## 🔧 Utilisation

### Lancer le notebook

```bash
marimo edit notebook.py
```

Le notebook s'ouvre dans votre navigateur avec une interface interactive.

### Workflow

1. **Upload du fichier CSV** : Glissez-déposez votre fichier R63 dans la zone de téléchargement
2. **Configuration des paramètres TURPE** : Ajustez les tarifs si nécessaire (valeurs par défaut fournies)
3. **Plage de puissances** : Définissez l'intervalle de puissances à tester (ex: 36-66 kW)
4. **Plages horaires HC** : Configurez les heures creuses (format : `02h00-07h00`)
5. **Analyse automatique** : Le notebook calcule et affiche :
   - Les statistiques de consommation par cadran tarifaire
   - La simulation pour toutes les puissances de la plage
   - Le graphique interactif des coûts
   - La recommandation optimale
6. **Export** : Téléchargez les résultats au format Excel

---

## 📈 Paramètres TURPE

Le notebook utilise les composantes tarifaires suivantes (modifiables via l'interface) :

### Composantes fixes annuelles

| Paramètre | Description | Valeur par défaut |
|-----------|-------------|-------------------|
| `CG` | Composante de gestion | 217,80 € |
| `CC` | Composante de comptage | 283,27 € |
| `CS_CU` | Coefficient pondérateur puissance CU | 17,61 €/kVA/an |
| `CS_LU` | Coefficient pondérateur puissance LU | 30,16 €/kVA/an |
| `CMDPS` | Coût mensuel dépassement | 12,41 €/h |
| `CTA` | Contribution Tarifaire d'Acheminement | 0,2193 (21,93%) |

### Composantes variables (c€/kWh)

| Cadran | CU | LU |
|--------|----|----|
| **HPH** (Heures Pleines Hiver) | 6,91 | 5,69 |
| **HCH** (Heures Creuses Hiver) | 4,21 | 3,47 |
| **HPB** (Heures Pleines Basse saison) | 2,13 | 2,01 |
| **HCB** (Heures Creuses Basse saison) | 1,52 | 1,49 |

**Saisons** :
- **Hiver (H)** : novembre à mars
- **Basse saison (B)** : avril à octobre

> ⚠️ **Note** : Ces tarifs évoluent régulièrement. Vérifiez sur le site de la CRE pour les valeurs à jour.

---

## 🧮 Calcul des coûts

### 1. Coût fixe annuel

**Courte Utilisation (CU)** :
```
Coût_fixe_CU = (CG + CC + CS_CU × P) × (1 + CTA)
```

**Longue Utilisation (LU)** :
```
Coût_fixe_LU = (CG + CC + CS_LU × P) × (1 + CTA)
```

### 2. Coût variable annuel

Pour chaque mesure :
```
Volume_kWh = Puissance_kW × Pas_heures
```

Coût variable total :
```
Coût_variable = Σ(Volume_cadran × Tarif_cadran)
```

Où les cadrans sont : HPH, HCH, HPB, HCB

### 3. Coût de dépassement

Pour chaque période où la puissance mesurée dépasse la puissance souscrite :
```
Coût_dépassement = Durée_dépassement_heures × CMDPS
```

### 4. Coût total annuel

```
Coût_total = Coût_fixe + Coût_variable + Coût_dépassement
```

---

## 📊 Interprétation des résultats

### Le graphique interactif

Affiche les courbes de coût total en fonction de la puissance souscrite :
- **Courbe bleue** : Option CU (Courte Utilisation)
- **Courbe orange** : Option LU (Longue Utilisation)

Les points correspondent aux puissances testées. Survolez-les pour voir les détails.

### La recommandation

Le notebook affiche automatiquement :
```
✅ RECOMMANDATION
Souscrire 52 kW en option LU
- Coût annuel : 1 180,45 €/an
- Économie vs autre option : 70,00 €/an
```

### Le fichier Excel exporté

Contient un tableau détaillé avec toutes les simulations :

| Colonne | Description |
|---------|-------------|
| `PS` | Puissance souscrite testée (kW) |
| `CU fixe` | Coût fixe annuel en option CU (€) |
| `LU fixe` | Coût fixe annuel en option LU (€) |
| `CU variable` | Coût variable annuel en option CU (€) |
| `LU variable` | Coût variable annuel en option LU (€) |
| `Dépassement` | Coût annuel des dépassements (€) |
| `Total CU` | Coût total annuel en option CU (€) |
| `Total LU` | Coût total annuel en option LU (€) |

---

## 🏗️ Architecture technique

### Structure du notebook

Le notebook Marimo est organisé en cellules réactives :

1. **Imports et configuration** - Librairies nécessaires
2. **Paramètres d'entrée** - Widgets interactifs pour la configuration
3. **Chargement des données brutes** - Parsing du CSV, validation
4. **Enrichissement** - Calcul des cadrans tarifaires, volumes par cadran
5. **Fonctions de calcul** - Expressions Polars pour les transformations
6. **Simulation** - Calcul des coûts pour chaque puissance
7. **Résultats** - Affichage graphique et recommandation
8. **Export** - Téléchargement Excel

### Technologies utilisées

- **Marimo** : Framework de notebooks réactifs (pas de cellule "en attente", tout est synchronisé)
- **Polars** : Manipulation ultra-rapide de DataFrames (alternative moderne à pandas)
- **Altair** : Visualisations déclaratives et interactives
- **Expressions Polars** : Transformations lazy et optimisées (pas de boucles Python)

### Avantages de l'approche

- ✅ **Réactivité** : Changez un paramètre, tout se recalcule automatiquement
- ✅ **Performance** : Polars traite des millions de lignes en secondes
- ✅ **Clarté** : Code fonctionnel avec expressions déclaratives
- ✅ **Reproductibilité** : Les notebooks Marimo sont des fichiers Python standards

---

## ⚙️ Personnalisation avancée

### Modifier les plages horaires HC

Format attendu : `HHhMM-HHhMM` séparé par `;`

Exemples :
- Une plage : `02h00-07h00`
- Deux plages : `02h00-07h00;22h00-06h00`
- Plage à cheval sur minuit : `22h00-06h00`

### Adapter les cadrans tarifaires

Les fonctions d'enrichissement se trouvent dans la cellule `fonctions_enrichissement` :
- `expr_saison()` : Détermine Hiver (H) ou Basse saison (B)
- `expr_horaire()` : Détermine Heures Pleines (HP) ou Heures Creuses (HC)
- `expr_cadran()` : Combine les deux (HPH, HCH, HPB, HCB)

Modifiez ces fonctions pour adapter à d'autres grilles tarifaires.

---

## 🐛 Résolution de problèmes

### Le fichier ne se charge pas
➡️ Vérifiez :
- Le séparateur est bien `;`
- Les colonnes requises sont présentes : `Horodate`, `Grandeur physique`, `Valeur`, `Pas`
- Les données PA (Puissance Active) sont présentes

### Erreur "Colonnes manquantes"
➡️ Le CSV doit contenir exactement les colonnes attendues du format Enedis R63

### Pas de données après filtrage
➡️ Assurez-vous que la colonne `Grandeur physique` contient des lignes avec la valeur `PA`

### Les cadrans ne sont pas corrects
➡️ Vérifiez le format des plages horaires HC (ex: `02h00-07h00`)

### Les coûts semblent anormaux
➡️ Vérifiez que les paramètres TURPE correspondent bien à votre tarif actuel

---

## 📚 Ressources

- [Documentation Marimo](https://docs.marimo.io)
- [Documentation Polars](https://pola-rs.github.io/polars-book/)

