#!/bin/bash

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Récupère le mot de passe (paramètre ou demande interactive)
if [ -n "$1" ]; then
    PASSWORD="$1"
else
    echo -n "Mot de passe pour les archives : "
    read -s PASSWORD
    echo
fi

# Compteurs
SUCCESS=0
FAILED=0
SKIPPED=0

# Traite tous les fichiers ZIP
for zipfile in *.zip; do
    # Vérifie que le fichier existe (au cas où aucun *.zip)
    [ -e "$zipfile" ] || continue

    # Détermine le nom du CSV qui sera extrait
    csv_name="${zipfile%.zip}.csv"
    csv_name="${csv_name#*-ENEDIS_}"
    csv_name="ENEDIS_${csv_name}"

    # Vérifie si le CSV existe déjà
    if [ -f "$csv_name" ]; then
        echo -e "${YELLOW}⊘ $zipfile déjà extrait (ignoré)${NC}"
        ((SKIPPED++))
        continue
    fi

    echo -e "${YELLOW}=== Extraction de $zipfile ===${NC}"

    if 7z x -p"$PASSWORD" -y "$zipfile" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $zipfile extrait avec succès${NC}"
        ((SUCCESS++))
    else
        # Même si 7z retourne une erreur, le fichier peut être extrait
        # On vérifie si le CSV correspondant existe maintenant
        if [ -f "$csv_name" ]; then
            echo -e "${GREEN}✓ $zipfile extrait (avec warnings)${NC}"
            ((SUCCESS++))
        else
            echo -e "${RED}✗ Échec pour $zipfile${NC}"
            ((FAILED++))
        fi
    fi
    echo
done

# Résumé
echo -e "${YELLOW}========== RÉSUMÉ ==========${NC}"
echo -e "${GREEN}Succès : $SUCCESS${NC}"
echo -e "${YELLOW}Ignorés : $SKIPPED${NC}"
echo -e "${RED}Échecs : $FAILED${NC}"
