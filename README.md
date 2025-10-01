# Optimisation TURPE - Calcul de Puissance Souscrite Optimale

## 📋 Vue d'ensemble

Cet outil permet de déterminer la **puissance souscrite optimale** pour un point de livraison électrique en fonction d'une courbe de charge réelle. Il simule les coûts d'acheminement (TURPE) pour différentes puissances et compare les options tarifaires **CU** (Courte Utilisation) et **LU** (Longue Utilisation).

### Objectif
Minimiser le coût annuel d'acheminement en trouvant le meilleur compromis entre :
- Les **coûts fixes** (qui augmentent avec la puissance souscrite)
- Les **coûts de dépassement** (qui diminuent avec une puissance souscrite plus élevée)

---

## 🚀 Installation

### Prérequis
- Python 3.7+
- pandas
- matplotlib
- openpyxl (pour l'export Excel)

### Installation des dépendances

```bash
pip install pandas matplotlib openpyxl
```

---

## 📊 Format du fichier d'entrée

Le script attend un fichier CSV au **format Enedis** avec les colonnes suivantes :

| Horodate | Grandeur physique | Valeur |
|----------|-------------------|--------|
| 2024-01-01 00:00:00 | PA | 45000 |
| 2024-01-01 00:10:00 | PA | 47500 |

### Spécifications
- **Séparateur** : point-virgule (`;`)
- **Horodate** : Format `YYYY-MM-DD HH:MM:SS`
- **Grandeur physique** : `PA` (Puissance Active)
- **Valeur** : Puissance en Watts (kVA)
- **Période** : Minimum 1 an de données pour une analyse complète

### Configuration
Modifiez la variable `FILE` dans le script pour pointer vers votre fichier :

```python
FILE = 'atalante.csv'  # Remplacez par le nom de votre fichier
```

---

## 🔧 Utilisation

### Exécution simple

```bash
python "opti C4.py"
```

### Sorties générées

1. **Graphique** : Affiche les courbes de coût total en fonction de la puissance souscrite (CU vs LU)
2. **Fichier Excel** : `Simulation.xlsx` contenant le tableau détaillé des simulations

---

## 📈 Paramètres TURPE (version actuelle)

Le script utilise les composantes tarifaires suivantes :

| Paramètre | Description | Valeur (€) |
|-----------|-------------|-----------|
| `CG` | Composante de gestion | 217,80 |
| `CC` | Composante de comptage | 283,27 |
| `CS_CU` | Composante de soutirage CU (€/kW) | 17,61 |
| `CS_LU` | Composante de soutirage LU (€/kW) | 30,16 |
| `CMDPS` | Coût de dépassement mensuel (€/h) | 12,41 |
| `CTA` | Contribution Tarifaire d'Acheminement | 1,2193 |

> ⚠️ **Note** : Ces tarifs évoluent régulièrement. Vérifiez sur le site de la CRE pour les valeurs à jour.

---

## 🧮 Calcul des coûts

### 1. Coût fixe annuel

**Courte Utilisation (CU)** :
```
Coût_fixe_CU = (CG + CC + CS_CU × P) × CTA
```

**Longue Utilisation (LU)** :
```
Coût_fixe_LU = (CG + CC + CS_LU × P) × CTA
```

### 2. Coût de dépassement

Pour chaque heure où la puissance mesurée dépasse la puissance souscrite :
```
Coût_dépassement = Nombre_heures_dépassement × CMDPS
```

### 3. Coût total annuel

```
Coût_total = Coût_fixe + Coût_dépassement
```

---

## 📊 Interprétation des résultats

### Le fichier Simulation.xlsx

| Colonne | Description |
|---------|-------------|
| `PS` | Puissance souscrite testée (kW) |
| `CU fixe` | Coût fixe annuel en option CU (€) |
| `LU fixe` | Coût fixe annuel en option LU (€) |
| `Dépassement` | Coût annuel des dépassements (€) |
| `Total CU` | Coût total annuel en option CU (€) |
| `Total LU` | Coût total annuel en option LU (€) |

### Comment choisir la puissance optimale ?

1. **Regardez le graphique** : Identifiez le point le plus bas de chaque courbe
2. **Comparez CU vs LU** : Déterminez quelle option tarifaire est la plus avantageuse
3. **Analysez le tableau** :
   - La puissance optimale CU correspond au minimum de la colonne `Total CU`
   - La puissance optimale LU correspond au minimum de la colonne `Total LU`

### Exemple d'analyse

```
Puissance optimale CU : 48 kW → 1 250 €/an
Puissance optimale LU : 52 kW → 1 180 €/an

→ Recommandation : Souscrire 52 kW en option LU (économie de 70 €/an)
```

---

## ⚙️ Personnalisation

### Modifier la plage de puissances testées

Par défaut, le script teste les puissances de 36 à 66 kW. Pour modifier :

```python
Ps = list(range(36, 66))  # Remplacez par votre plage souhaitée
# Exemple : Ps = list(range(20, 100))  # Teste de 20 à 100 kW
```

### Mettre à jour les tarifs TURPE

Modifiez les constantes en début de script avec les tarifs actuels :

```python
CG = 217.8
CC = 283.27
CS_CU = 17.61
CS_LU = 30.16
CMDPS = 12.41
CTA = 1.2193
```

---

## 🐛 Résolution de problèmes

### Erreur : `FileNotFoundError`
➡️ Vérifiez que le fichier CSV existe et que le nom est correct dans `FILE`

### Erreur : `KeyError: 'Grandeur physique'`
➡️ Vérifiez que le fichier CSV contient bien les colonnes attendues

### Le graphique ne s'affiche pas
➡️ Ajoutez `plt.show()` à la fin du script ou exécutez dans un environnement interactif

### Résultats incohérents
➡️ Assurez-vous d'avoir au moins 1 an de données dans la courbe de charge

---

## 📚 Ressources

- [Tarifs TURPE - CRE](https://www.cre.fr/Electricite/Reseaux-d-electricite/tarifs-d-acces-aux-reseaux-publics-d-electricite)
- [Format des données Enedis](https://www.enedis.fr/courbe-de-charge)

---

## 📝 Notes importantes

- ⚠️ La variable `P` (ligne 66) n'est pas définie dans le script actuel. Elle doit être initialisée ou le code corrigé pour fonctionner correctement.
- 📅 Les données doivent couvrir une période d'un an pour une simulation représentative
- 💡 L'option CU est généralement plus avantageuse pour les faibles utilisations, LU pour les fortes utilisations

---

## 🤝 Support

Pour toute question ou amélioration, contactez l'auteur : Hamza
