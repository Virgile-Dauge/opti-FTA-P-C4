import marimo

__generated_with = "0.16.3"
app = marimo.App(width="medium")

async with app.setup:
    # Initialization code that runs before all other cells

    # Installation des dépendances pour WASM (Pyodide)
    import sys
    if "pyodide" in sys.modules:
        import micropip
        await micropip.install("pyarrow")
        await micropip.install("xlsxwriter")
        # electricore 1.2.0+ avec core minimal compatible WASM
        await micropip.install("electricore==1.3.3", keep_going=True)

    # Imports standards
    import marimo as mo
    import polars as pl
    from pathlib import Path
    from datetime import datetime, time
    import io

    # Import electricore pour calculs TURPE
    from electricore.core.pipelines.turpe import (
        ajouter_turpe_fixe,
        ajouter_turpe_variable,
        load_turpe_rules,
    )

    # Import pour optimisation multi-cadrans
    from itertools import combinations_with_replacement


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
    # 🔌 Optimisation TURPE avec electricore - Calcul Multi-Scénarios

    Cet outil permet de déterminer la **puissance souscrite et formule tarifaire optimales**
    pour un ou plusieurs points de livraison électriques en fonction des courbes de charge réelles.

    Il simule les coûts d'acheminement (TURPE) pour :
    - **Différentes puissances** (3 à 250 kVA)
    - **Différentes formules tarifaires** (CU, MU, LU - selon la puissance)
    - **Catégories C4 et C5** (avec pénalités de dépassement pour C4)

    Les calculs utilisent **electricore v1.1.0** avec les tarifs TURPE officiels.
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md("""## 📂 Upload de la courbe de charge""")
    return


@app.cell(hide_code=True)
def _():
    file_upload = mo.ui.file(
        filetypes=[".csv"],
        kind="area",
        label="Sélectionnez votre fichier CSV R63 (format Enedis)"
    )
    file_upload
    return (file_upload,)


@app.cell(hide_code=True)
def _():
    mo.md("""## ⏰ Plages horaires tarifaires""")
    return


@app.cell(hide_code=True)
def _():
    plage_hc_input = mo.ui.text(
        value="22h00-06h00",
        label="Plages horaires Heures Creuses (HC)",
        placeholder="Ex: 02h00-07h00 ou 02h00-07h00;22h00-06h00",
        full_width=True
    )
    plage_hc_input
    return (plage_hc_input,)


@app.cell(hide_code=True)
def _(plage_hc_input):
    # Parser les plages horaires une seule fois
    def parser_plages_horaires(plage_str: str) -> list[tuple[time, time]]:
        """
        Parse une chaîne de plages horaires format Enedis.

        Format : "08h00-12h00;14h00-18h00"

        Returns:
            Liste de tuples (heure_debut, heure_fin)
        """
        if not plage_str or plage_str.strip() == '':
            return []

        plage_str = plage_str.replace(' ', '').replace('(', '').replace(')', '')
        plages = []

        for slot in plage_str.split(';'):
            if '-' not in slot:
                continue
            start_str, end_str = slot.split('-')
            start_time = datetime.strptime(start_str, '%Hh%M').time()
            end_time = datetime.strptime(end_str, '%Hh%M').time()
            plages.append((start_time, end_time))

        return plages

    plages_hc = parser_plages_horaires(plage_hc_input.value)
    return (plages_hc,)


@app.cell(hide_code=True)
def _():
    mo.md("""## 📊 Plage de puissances à tester""")
    return


@app.cell(hide_code=True)
def _():
    plage_puissance = mo.ui.range_slider(
        start=3,
        stop=250,
        step=1,
        value=[3, 250],
        label="Puissances à simuler (kVA)",
        show_value=True
    )

    plage_puissance
    return (plage_puissance,)


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
    ## 📋 Configuration actuelle (optionnel)

    Saisissez votre configuration tarifaire actuelle pour comparer avec l'optimum recommandé.
    """
    )
    return


@app.cell
def _():
    # Dropdown FTA
    fta_actuel = mo.ui.dropdown(
        options={
            'BTINFCU4': 'BTINFCU4',
            'BTINFMU4': 'BTINFMU4',
            'BTINFLU': 'BTINFLU',
            'BTSUPCU': 'BTSUPCU',
            'BTSUPLU': 'BTSUPLU'
        },
        value='BTSUPCU',
        label="Formule tarifaire actuelle"
    )

    # Inputs pour puissances
    # Mono-puissance (BTINF)
    puissance_actuelle_mono = mo.ui.number(
        value=36,
        start=3,
        stop=250,
        step=1,
        label="Puissance souscrite (kVA)"
    )

    # Multi-cadrans (BTSUP)
    puissance_actuelle_hph = mo.ui.number(value=36, start=36, stop=250, step=1, label="HPH (kVA)")
    puissance_actuelle_hch = mo.ui.number(value=40, start=36, stop=250, step=1, label="HCH (kVA)")
    puissance_actuelle_hpb = mo.ui.number(value=45, start=36, stop=250, step=1, label="HPB (kVA)")
    puissance_actuelle_hcb = mo.ui.number(value=50, start=36, stop=250, step=1, label="HCB (kVA)")
    return (
        fta_actuel,
        puissance_actuelle_hcb,
        puissance_actuelle_hch,
        puissance_actuelle_hpb,
        puissance_actuelle_hph,
        puissance_actuelle_mono,
    )


@app.cell(hide_code=True)
def _(
    fta_actuel,
    puissance_actuelle_hcb,
    puissance_actuelle_hch,
    puissance_actuelle_hpb,
    puissance_actuelle_hph,
    puissance_actuelle_mono,
):
    # Affichage conditionnel
    _is_btinf = fta_actuel.value in ['BTINFCU4', 'BTINFMU4', 'BTINFLU']

    if _is_btinf:
        _msg = mo.vstack([fta_actuel, puissance_actuelle_mono])
    else:
        _msg = mo.vstack([
            fta_actuel,
            mo.md("**Puissances souscrites par cadran tarifaire :**"),
            mo.hstack([puissance_actuelle_hph, puissance_actuelle_hch]),
            mo.hstack([puissance_actuelle_hpb, puissance_actuelle_hcb])
        ])
    _msg
    return


@app.cell
def _():
    mo.md(r"""## 📥 Traitement de la courbe de charge""")
    return


@app.cell(hide_code=True)
def _(expr_cadran, expr_pas_heures, expr_volume, file_upload, plages_hc):
    mo.stop(not file_upload.value, mo.md("⚠️ Veuillez uploader un fichier CSV"))

    # Écrire le CSV dans un fichier temporaire pour scan_csv
    import tempfile
    csv_content = file_upload.contents()
    _temp_csv = tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False)
    _temp_csv.write(csv_content)
    _temp_csv.close()

    # Pipeline LAZY complet - AUCUN collect()
    cdc_lazy = (
        pl.scan_csv(_temp_csv.name, separator=';')
        .filter(pl.col('Grandeur physique') == 'PA')
        .with_columns([
            pl.col('Horodate').str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S'),
            (pl.col('Valeur') / 1000.0).alias('Valeur'),
        ])
        .with_columns([
            expr_pas_heures().alias('pas_heures')
        ])
        .with_columns([
            expr_volume().alias('volume'),
            expr_cadran(plages_hc).alias('cadran')
        ])
        .select(['Valeur', 'pas_heures', 'cadran', 'Horodate', 'Identifiant PRM', 'volume'])
    )
    return (cdc_lazy,)


@app.cell(hide_code=True)
def fonctions_enrichissement():
    """Fonctions utilitaires pour enrichir la courbe de charge avec cadrans horaires."""

    def expr_pas_heures() -> pl.Expr:
        """
        Expression Polars pour calculer le pas en heures à partir de la colonne 'Pas'.

        Convertit 'PT5M' → 5/60 = 0.0833 heures

        Returns:
            Expression Polars du pas en heures
        """
        return (
            pl.col('Pas')
            .str.strip_prefix('PT')
            .str.strip_suffix('M')
            .cast(pl.Int32)
            / 60.0
        )

    def expr_volume() -> pl.Expr:
        """
        Expression Polars pour calculer le volume en kWh.

        volume = Valeur (kW) × pas_heures (h)

        Returns:
            Expression Polars du volume en kWh
        """
        return pl.col('Valeur') * pl.col('pas_heures')

    def expr_saison() -> pl.Expr:
        """
        Expression Polars pour déterminer la saison tarifaire.

        - H (Hiver) : novembre à mars (mois < 4 ou > 10)
        - B (Été/Basse) : avril à octobre (mois 4-10)

        Returns:
            Expression Polars retournant 'H' ou 'B'
        """
        return pl.when(
            (pl.col('Horodate').dt.month() < 4) | (pl.col('Horodate').dt.month() > 10)
        ).then(pl.lit('H')).otherwise(pl.lit('B'))

    def expr_horaire(plages: list[tuple[time, time]]) -> pl.Expr:
        """
        Expression Polars pour déterminer si en Heures Creuses (HC) ou Heures Pleines (HP).

        Args:
            plages: Liste de tuples (heure_debut, heure_fin) pour les HC

        Returns:
            Expression Polars retournant 'HC' ou 'HP'
        """
        if not plages:
            # Pas de plages HC définies = tout en HP
            return pl.lit('HP')

        # Construire la condition : True si dans une des plages HC
        condition = pl.lit(False)

        for start_time, end_time in plages:
            heure_courante = pl.col('Horodate').dt.time()

            if start_time < end_time:
                # Plage normale (ex: 02h00-07h00)
                condition = condition | (
                    (heure_courante >= start_time) & (heure_courante <= end_time)
                )
            else:
                # Plage à cheval sur minuit (ex: 22h00-06h00)
                condition = condition | (
                    (heure_courante >= start_time) | (heure_courante <= end_time)
                )

        return pl.when(condition).then(pl.lit('HC')).otherwise(pl.lit('HP'))

    def expr_cadran(plages: list[tuple[time, time]]) -> pl.Expr:
        """
        Expression Polars pour déterminer le cadran tarifaire complet.

        Cadrans possibles : HPH, HCH, HPB, HCB

        Args:
            plages: Liste de tuples (heure_debut, heure_fin) pour les HC

        Returns:
            Expression Polars retournant le cadran (ex: 'HPH', 'HCB')
        """
        return expr_horaire(plages) + expr_saison()
    return expr_cadran, expr_pas_heures, expr_volume


@app.cell
def _(cdc_lazy):
    cdc_lazy.collect()
    return


@app.cell
def _():
    mo.md(r"""## 🔄 Agrégation par PDL et pivotage des cadrans""")
    return


@app.cell(hide_code=True)
def _(cdc_lazy):
    # Étape 1: Calculer les dates globales par PDL (AVANT le pivot)
    dates_pdl = (
        cdc_lazy
        .group_by('Identifiant PRM')
        .agg([
            pl.col('Horodate').min().alias('date_debut'),
            pl.col('Horodate').max().alias('date_fin'),
            pl.col('Valeur').max().alias('pmax_moyenne_kva'),
        ])
        .collect()
    )

    # Étape 2: Agrégation des énergies et pmax par PDL et cadran
    energies_par_cadran = (
        cdc_lazy
        .group_by(['Identifiant PRM', 'cadran'])
        .agg([
            pl.col('volume').sum().alias('energie_kwh'),
            pl.col('Valeur').max().alias('pmax_cadran_kva'),
        ])
        .collect()
    )

    # Étape 3a: Pivot des énergies
    energies_pivot = energies_par_cadran.pivot(
        on='cadran',
        index='Identifiant PRM',
        values='energie_kwh',
    )

    # Étape 3b: Pivot des pmax par cadran
    pmax_pivot = energies_par_cadran.pivot(
        on='cadran',
        index='Identifiant PRM',
        values='pmax_cadran_kva',
    )

    # Étape 3c: Joindre tout
    consos_agregees = (
        energies_pivot
        .join(dates_pdl, on='Identifiant PRM', how='left')
        .join(
            pmax_pivot.rename({
                'HPH': 'pmax_hph_kva',
                'HCH': 'pmax_hch_kva',
                'HPB': 'pmax_hpb_kva',
                'HCB': 'pmax_hcb_kva',
            }),
            on='Identifiant PRM',
            how='left'
        )
        # Renommer pour format electricore
        .rename({
            'Identifiant PRM': 'pdl',
            'HPH': 'energie_hph_kwh',
            'HCH': 'energie_hch_kwh',
            'HPB': 'energie_hpb_kwh',
            'HCB': 'energie_hcb_kwh',
        })
        # Remplir les valeurs manquantes par 0 (si un cadran n'existe pas)
        .with_columns([
            # Calculer le nombre de jours de la période
            (pl.col('date_fin') - pl.col('date_debut')).dt.total_days().alias('nb_jours'),
            pl.col('energie_hph_kwh').fill_null(0).floor(),
            pl.col('energie_hch_kwh').fill_null(0).floor(),
            pl.col('energie_hpb_kwh').fill_null(0).floor(),
            pl.col('energie_hcb_kwh').fill_null(0).floor(),
            # Estimation pmax globale à partir de la puissance moyenne sur 5 min (heuristique × 1.15)
            (pl.col('pmax_moyenne_kva') * 1.15).alias('pmax_estimee_kva'),
            # Estimation pmax par cadran avec même heuristique
            (pl.col('pmax_hph_kva') * 1.15).fill_null(0).alias('pmax_hph_estimee_kva'),
            (pl.col('pmax_hch_kva') * 1.15).fill_null(0).alias('pmax_hch_estimee_kva'),
            (pl.col('pmax_hpb_kva') * 1.15).fill_null(0).alias('pmax_hpb_estimee_kva'),
            (pl.col('pmax_hcb_kva') * 1.15).fill_null(0).alias('pmax_hcb_estimee_kva'),
        ])
    )

    _nb_pdl = len(consos_agregees)
    _energie_totale = (
        consos_agregees['energie_hph_kwh'].sum() +
        consos_agregees['energie_hch_kwh'].sum() +
        consos_agregees['energie_hpb_kwh'].sum() +
        consos_agregees['energie_hcb_kwh'].sum()
    )

    mo.md(f"""
    ✅ **Agrégation terminée**

    - Nombre de PDL : {_nb_pdl}
    - Énergie totale : {_energie_totale:,.0f} kWh
    """)
    return (consos_agregees,)


@app.cell
def _(consos_agregees):
    consos_agregees
    return


@app.cell
def _():
    mo.md(r"""## 🎯 Génération des scénarios d'optimisation""")
    return


@app.function(hide_code=True)
def generer_scenarios_reduction_proportionnelle(consos_agregees: pl.DataFrame) -> pl.DataFrame:
    """
    Génère les scénarios multi-cadrans par réduction proportionnelle simultanée.

    Principe :
    - Part de (pmax_hph, pmax_hch, pmax_hpb, pmax_hcb) × 1.15 arrondi
    - Applique la contrainte P_hph ≤ P_hch ≤ P_hpb ≤ P_hcb
    - Réduit toutes les puissances de 1 kVA simultanément jusqu'à ce que le min atteigne 36

    Hypothèse : Le profil de charge est similaire entre cadrans (seule l'amplitude diffère)
    """
    from math import ceil

    scenarios_list = []

    for row in consos_agregees.iter_rows(named=True):
        # Étape 1 : Calculer les puissances de base (pmax × 1.15)
        p_hph_base = int(ceil(row['pmax_hph_estimee_kva']))
        p_hch_base = int(ceil(row['pmax_hch_estimee_kva']))
        p_hpb_base = int(ceil(row['pmax_hpb_estimee_kva']))
        p_hcb_base = int(ceil(row['pmax_hcb_estimee_kva']))

        # Étape 2 : Forcer la contrainte d'ordre (cascade)
        p_hph_initial = max(36, p_hph_base)
        p_hch_initial = max(p_hph_initial, p_hch_base)
        p_hpb_initial = max(p_hch_initial, p_hpb_base)
        p_hcb_initial = max(p_hpb_initial, p_hcb_base)

        # Étape 3 : Le minimum détermine le nombre d'itérations
        p_min_initial = min(p_hph_initial, p_hch_initial, p_hpb_initial, p_hcb_initial)
        nb_iterations = p_min_initial - 36 + 1  # Jusqu'à ce que le min atteigne 36

        # Étape 4 : Générer toutes les configurations par réduction simultanée
        for i in range(nb_iterations):
            reduction = i
            config = {
                'pdl': row['pdl'],
                'energie_hph_kwh': row['energie_hph_kwh'],
                'energie_hch_kwh': row['energie_hch_kwh'],
                'energie_hpb_kwh': row['energie_hpb_kwh'],
                'energie_hcb_kwh': row['energie_hcb_kwh'],
                'puissance_hph_kva': max(36, p_hph_initial - reduction),
                'puissance_hch_kva': max(36, p_hch_initial - reduction),
                'puissance_hpb_kva': max(36, p_hpb_initial - reduction),
                'puissance_hcb_kva': max(36, p_hcb_initial - reduction),
                'iteration': i,
            }
            scenarios_list.append(config)

    # Créer DataFrame
    df_scenarios = pl.DataFrame(scenarios_list)

    # Ajouter dates, FTA, etc.
    df_scenarios = (
        df_scenarios
        .with_columns([
            pl.lit(datetime(2025, 8, 1)).dt.replace_time_zone('Europe/Paris').alias('date_debut'),
            pl.lit(datetime(2026, 7, 31)).dt.replace_time_zone('Europe/Paris').alias('date_fin'),
            pl.lit(365).alias('nb_jours'),
            pl.lit(['BTSUPCU', 'BTSUPLU']).alias('formule_tarifaire_acheminement'),
        ])
        .explode('formule_tarifaire_acheminement')
        .with_columns([
            pl.col('puissance_hcb_kva').alias('puissance_souscrite_kva'),  # Max pour compatibilité
        ])
    )

    return df_scenarios


@app.cell(hide_code=True)
def _(
    cdc_lazy,
    consos_agregees,
    fta_actuel,
    puissance_actuelle_hcb,
    puissance_actuelle_hch,
    puissance_actuelle_hpb,
    puissance_actuelle_hph,
    puissance_actuelle_mono,
):
    # Génération du scénario actuel pour comparaison

    # Collecter cdc pour le calcul de dépassement
    _cdc_actuel = cdc_lazy.select(['Valeur', 'pas_heures', 'cadran']).collect()

    # Récupérer les énergies depuis consos_agregees (1 ligne par PDL)
    _row_actuel = consos_agregees[0]

    # Déterminer si mono ou multi-puissance
    _is_btinf_actuel = fta_actuel.value in ['BTINFCU4', 'BTINFMU4', 'BTINFLU']

    if _is_btinf_actuel:
        # Mono-puissance
        _p_mono = float(puissance_actuelle_mono.value)
        _scenario_actuel_dict = {
            'pdl': _row_actuel['pdl'][0],
            'energie_hph_kwh': float(_row_actuel['energie_hph_kwh'][0]),
            'energie_hch_kwh': float(_row_actuel['energie_hch_kwh'][0]),
            'energie_hpb_kwh': float(_row_actuel['energie_hpb_kwh'][0]),
            'energie_hcb_kwh': float(_row_actuel['energie_hcb_kwh'][0]),
            'puissance_souscrite_kva': _p_mono,
            'puissance_hph_kva': _p_mono,
            'puissance_hch_kva': _p_mono,
            'puissance_hpb_kva': _p_mono,
            'puissance_hcb_kva': _p_mono,
            'formule_tarifaire_acheminement': fta_actuel.value,
            'date_debut': datetime(2025, 8, 1),
            'date_fin': datetime(2026, 7, 31),
            'nb_jours': 365,
        }
    else:
        # Multi-cadrans
        _scenario_actuel_dict = {
            'pdl': _row_actuel['pdl'][0],
            'energie_hph_kwh': float(_row_actuel['energie_hph_kwh'][0]),
            'energie_hch_kwh': float(_row_actuel['energie_hch_kwh'][0]),
            'energie_hpb_kwh': float(_row_actuel['energie_hpb_kwh'][0]),
            'energie_hcb_kwh': float(_row_actuel['energie_hcb_kwh'][0]),
            'puissance_hph_kva': float(puissance_actuelle_hph.value),
            'puissance_hch_kva': float(puissance_actuelle_hch.value),
            'puissance_hpb_kva': float(puissance_actuelle_hpb.value),
            'puissance_hcb_kva': float(puissance_actuelle_hcb.value),
            'puissance_souscrite_kva': float(puissance_actuelle_hcb.value),  # Max
            'formule_tarifaire_acheminement': fta_actuel.value,
            'date_debut': datetime(2025, 8, 1),
            'date_fin': datetime(2026, 7, 31),
            'nb_jours': 365,
        }

    # Calculer dépassement
    _duree_depassement_actuel = calculer_duree_depassement_par_cadran(
        _cdc_actuel,
        _scenario_actuel_dict['puissance_hph_kva'],
        _scenario_actuel_dict['puissance_hch_kva'],
        _scenario_actuel_dict['puissance_hpb_kva'],
        _scenario_actuel_dict['puissance_hcb_kva']
    )
    _scenario_actuel_dict['duree_depassement_h'] = _duree_depassement_actuel

    # Créer DataFrame avec colonnes dans le même ordre que scenarios
    scenario_actuel = (
        pl.DataFrame([_scenario_actuel_dict])
        .with_columns([
            # Ajouter timezone pour compatibilité avec scenarios
            pl.col('date_debut').dt.replace_time_zone('Europe/Paris'),
            pl.col('date_fin').dt.replace_time_zone('Europe/Paris'),
            # Forcer les types numériques
            pl.col('nb_jours').cast(pl.Int32),
            pl.col('energie_hph_kwh').cast(pl.Float64),
            pl.col('energie_hch_kwh').cast(pl.Float64),
            pl.col('energie_hpb_kwh').cast(pl.Float64),
            pl.col('energie_hcb_kwh').cast(pl.Float64),
            pl.col('puissance_souscrite_kva').cast(pl.Int64),
            pl.col('puissance_hph_kva').cast(pl.Int64),
            pl.col('puissance_hch_kva').cast(pl.Int64),
            pl.col('puissance_hpb_kva').cast(pl.Int64),
            pl.col('puissance_hcb_kva').cast(pl.Int64),
            pl.col('duree_depassement_h').cast(pl.Float64),
        ])
        .select([
            'pdl', 'energie_hph_kwh', 'energie_hch_kwh', 'energie_hpb_kwh', 'energie_hcb_kwh',
            'date_debut', 'date_fin', 'nb_jours',
            'puissance_souscrite_kva', 'formule_tarifaire_acheminement', 'duree_depassement_h',
            'puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva'
        ])
    )
    return (scenario_actuel,)


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(cdc_lazy, consos_agregees, plage_puissance):
    # Génération des scénarios multi-cadrans par réduction proportionnelle

    P_min, P_max = plage_puissance.value

    # OPTIMISATION : Collect cdc_lazy UNE SEULE FOIS pour tous les calculs de dépassement
    # Sélectionner uniquement les 3 colonnes nécessaires avant collect
    cdc = cdc_lazy.select(['Valeur', 'pas_heures', 'cadran']).collect()

    # Mode multi-cadrans: réduction proportionnelle simultanée

    # Étape 1: Scénarios BTINF mono-puissance (< 36 kVA) si nécessaire
    scenarios_btinf = None
    if P_min < 36:
        puissances_btinf = list(range(P_min, min(36, P_max + 1)))
        scenarios_btinf = (
            consos_agregees
            .select(['pdl', 'energie_hph_kwh', 'energie_hch_kwh',
                     'energie_hpb_kwh', 'energie_hcb_kwh', 'pmax_estimee_kva'])
            .with_columns([
                pl.lit(datetime(2025, 8, 1)).dt.replace_time_zone('Europe/Paris').alias('date_debut'),
                pl.lit(datetime(2026, 7, 31)).dt.replace_time_zone('Europe/Paris').alias('date_fin'),
                pl.lit(365).alias('nb_jours'),
                pl.lit(puissances_btinf).alias('puissance_souscrite_kva')
            ])
            .explode('puissance_souscrite_kva')
            .with_columns([
                pl.lit(['BTINFCU4', 'BTINFMU4', 'BTINFLU']).alias('formule_tarifaire_acheminement')
            ])
            .explode('formule_tarifaire_acheminement')
            .filter(pl.col('puissance_souscrite_kva') >= pl.col('pmax_estimee_kva'))
            .with_columns([
                # Remplir les 4 colonnes avec la puissance mono pour BTINF
                pl.col('puissance_souscrite_kva').alias('puissance_hph_kva'),
                pl.col('puissance_souscrite_kva').alias('puissance_hch_kva'),
                pl.col('puissance_souscrite_kva').alias('puissance_hpb_kva'),
                pl.col('puissance_souscrite_kva').alias('puissance_hcb_kva'),
            ])
            .with_columns([
                # Calculer durée dépassement avec les 4 puissances par cadran
                pl.struct(['puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva'])
                .map_elements(
                    lambda row: calculer_duree_depassement_par_cadran(
                        cdc,
                        row['puissance_hph_kva'],
                        row['puissance_hch_kva'],
                        row['puissance_hpb_kva'],
                        row['puissance_hcb_kva']
                    ),
                    return_dtype=pl.Float64
                )
                .alias('duree_depassement_h')
            ])
        )

    # Étape 2: Scénarios BTSUP multi-cadrans (≥ 36 kVA) - Réduction proportionnelle
    scenarios_btsup = generer_scenarios_reduction_proportionnelle(consos_agregees)

    # Calculer dépassements pour BTSUP
    scenarios_btsup = scenarios_btsup.with_columns([
        pl.struct(['puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva'])
        .map_elements(
            lambda row: calculer_duree_depassement_par_cadran(
                cdc,
                row['puissance_hph_kva'],
                row['puissance_hch_kva'],
                row['puissance_hpb_kva'],
                row['puissance_hcb_kva']
            ),
            return_dtype=pl.Float64
        )
        .alias('duree_depassement_h')
    ])

    # Harmoniser l'ordre des colonnes avant concat
    colonnes_ordre = [
        'pdl', 'energie_hph_kwh', 'energie_hch_kwh', 'energie_hpb_kwh', 'energie_hcb_kwh',
        'date_debut', 'date_fin', 'nb_jours',
        'puissance_souscrite_kva', 'formule_tarifaire_acheminement', 'duree_depassement_h',
        'puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva'
    ]

    # Ajouter pmax_estimee_kva si nécessaire pour BTINF
    if 'pmax_estimee_kva' in scenarios_btsup.columns:
        scenarios_btsup = scenarios_btsup.select(colonnes_ordre + ['pmax_estimee_kva'])
    else:
        scenarios_btsup = scenarios_btsup.select(colonnes_ordre)

    # Concaténer BTINF et BTSUP
    if scenarios_btinf is not None:
        colonnes_communes = [col for col in colonnes_ordre if col in scenarios_btinf.columns]
        scenarios_btinf = scenarios_btinf.select(colonnes_communes)
        scenarios_btsup = scenarios_btsup.select(colonnes_communes)
        scenarios = pl.concat([scenarios_btinf, scenarios_btsup])
    else:
        scenarios = scenarios_btsup

    _nb_scenarios_btsup = len(scenarios_btsup)
    _info = f"Multi-cadrans réduction proportionnelle: {_nb_scenarios_btsup} scénarios BTSUP"

    _nb_scenarios = len(scenarios)
    _nb_pdl = scenarios['pdl'].n_unique()

    mo.md(f"""
    ✅ **Scénarios générés**

    - {_info}
    - Nombre de scénarios : {_nb_scenarios:,}
    - PDL : {_nb_pdl}
    - FTA testées : BTINFCU4, BTINFMU4, BTINFLU (< 36 kVA) + BTSUPCU, BTSUPLU (≥ 36 kVA)
    """)
    return (scenarios,)


@app.function(hide_code=True)
# Fonction pour calculer la durée de dépassement par cadran
def calculer_duree_depassement_par_cadran(
    cdc: pl.DataFrame,
    puissance_hph_kva: float,
    puissance_hch_kva: float,
    puissance_hpb_kva: float,
    puissance_hcb_kva: float
) -> float:
    """
    Calcule la durée totale de dépassement en tenant compte des puissances par cadran.

    Args:
        cdc: DataFrame avec colonnes 'Valeur' (kW), 'pas_heures', 'cadran'
        puissance_hph_kva, puissance_hch_kva, puissance_hpb_kva, puissance_hcb_kva:
            Puissances souscrites par cadran (kVA)

    Returns:
        Durée totale de dépassement en heures (somme sur tous les cadrans)
    """
    return (
        cdc
        .with_columns([
            # Mapper chaque cadran à sa puissance souscrite
            pl.when(pl.col('cadran') == 'HPH').then(pl.lit(puissance_hph_kva))
            .when(pl.col('cadran') == 'HCH').then(pl.lit(puissance_hch_kva))
            .when(pl.col('cadran') == 'HPB').then(pl.lit(puissance_hpb_kva))
            .when(pl.col('cadran') == 'HCB').then(pl.lit(puissance_hcb_kva))
            .otherwise(pl.lit(puissance_hcb_kva))  # Défaut: utiliser la puissance max (HCB)
            .alias('puissance_seuil')
        ])
        # Ne compter que les dépassements (Valeur > seuil du cadran)
        .filter(pl.col('Valeur') > pl.col('puissance_seuil'))
        .select(pl.col('pas_heures').sum())
        .item()
    )


@app.cell
def _(scenarios):
    scenarios
    return


@app.cell
def _():
    mo.md(r"""## 🧮 Calcul TURPE avec electricore""")
    return


@app.cell(hide_code=True)
def _(scenario_actuel, scenarios):
    # Charger les règles TURPE une seule fois
    regles_turpe = load_turpe_rules()

    # Concaténer scénario actuel avec les scénarios d'optimisation
    tous_scenarios = pl.concat([scenario_actuel, scenarios])

    # Calcul TURPE via electricore sur tous les scénarios
    resultats_tous = (
        tous_scenarios
        .rename({
            'date_debut': 'debut',
            'date_fin': 'fin'
        })
        .with_columns([
            # Ajouter timezone Europe/Paris pour compatibilité avec electricore
            pl.col('debut').dt.replace_time_zone('Europe/Paris').alias('debut'),
            pl.col('fin').dt.replace_time_zone('Europe/Paris').alias('fin'),
        ])
        .with_columns([
            # Ajouter les colonnes agrégées pour formules C5 (HP/HC/Base)
            (pl.col('energie_hph_kwh') + pl.col('energie_hpb_kwh')).alias('energie_hp_kwh'),
            (pl.col('energie_hch_kwh') + pl.col('energie_hcb_kwh')).alias('energie_hc_kwh'),
            (pl.col('energie_hph_kwh') + pl.col('energie_hch_kwh') +
             pl.col('energie_hpb_kwh') + pl.col('energie_hcb_kwh')).alias('energie_base_kwh'),
            # Pour C4 : les colonnes puissance_*_kva existent toujours maintenant
            # On les renomme juste en puissance_souscrite_*_kva pour electricore
            pl.col('puissance_hph_kva').alias('puissance_souscrite_hph_kva'),
            pl.col('puissance_hch_kva').alias('puissance_souscrite_hch_kva'),
            pl.col('puissance_hpb_kva').alias('puissance_souscrite_hpb_kva'),
            pl.col('puissance_hcb_kva').alias('puissance_souscrite_hcb_kva'),
        ])
        .lazy()
        .pipe(ajouter_turpe_fixe, regles=regles_turpe)
        .pipe(ajouter_turpe_variable, regles=regles_turpe)
        .with_columns([
            (pl.col('turpe_fixe_eur') + pl.col('turpe_variable_eur')).alias('turpe_total_eur')
        ])
        .collect()
    )

    # Séparer scénario actuel vs résultats d'optimisation
    cout_actuel = resultats_tous[0]  # Première ligne = scénario actuel
    resultats = resultats_tous[1:]  # Reste = scénarios d'optimisation

    _nb_resultats = len(resultats)
    _cout_min = resultats['turpe_total_eur'].min()
    _cout_max = resultats['turpe_total_eur'].max()
    _cout_actuel_val = cout_actuel['turpe_total_eur'][0]

    mo.md(f"""
    ✅ **Calculs TURPE terminés**

    - Scénarios calculés : {_nb_resultats:,}
    - **Coût actuel** : **{_cout_actuel_val:,.2f} €/an**
    - Coût min (optimisé) : {_cout_min:.2f} €/an
    - Coût max : {_cout_max:.2f} €/an
    """)
    return cout_actuel, resultats


@app.cell
def _(resultats):
    resultats
    return


@app.cell
def _():
    mo.md(r"""## 🎯 Résultats et recommandations""")
    return


@app.cell(hide_code=True)
def _(cout_actuel, resultats):
    # Trouver l'optimum global (toutes FTA confondues)
    idx_opt = resultats['turpe_total_eur'].arg_min()
    optimum = resultats[idx_opt]

    # Calculer économies
    economie_annuelle = cout_actuel['turpe_total_eur'][0] - optimum['turpe_total_eur'][0]
    economie_pct = (economie_annuelle / cout_actuel['turpe_total_eur'][0]) * 100

    # Affichage des puissances pour actuel et optimum
    fta_actuel_val = cout_actuel['formule_tarifaire_acheminement'][0]
    fta_opt = optimum['formule_tarifaire_acheminement'][0]

    is_multi_actuel = fta_actuel_val.startswith('BTSUP')
    is_multi_opt = fta_opt.startswith('BTSUP')

    if is_multi_actuel:
        puissances_actuel = f"{cout_actuel['puissance_hph_kva'][0]:.0f} / {cout_actuel['puissance_hch_kva'][0]:.0f} / {cout_actuel['puissance_hpb_kva'][0]:.0f} / {cout_actuel['puissance_hcb_kva'][0]:.0f} kVA"
    else:
        puissances_actuel = f"{cout_actuel['puissance_souscrite_kva'][0]:.0f} kVA"

    if is_multi_opt:
        puissances_opt = f"{optimum['puissance_hph_kva'][0]:.0f} / {optimum['puissance_hch_kva'][0]:.0f} / {optimum['puissance_hpb_kva'][0]:.0f} / {optimum['puissance_hcb_kva'][0]:.0f} kVA"
        puissances_detail_opt = f"""
    - **Puissances souscrites par cadran** :
      - HPH : **{optimum['puissance_hph_kva'][0]:.0f} kVA**
      - HCH : **{optimum['puissance_hch_kva'][0]:.0f} kVA**
      - HPB : **{optimum['puissance_hpb_kva'][0]:.0f} kVA**
      - HCB : **{optimum['puissance_hcb_kva'][0]:.0f} kVA**
    """
    else:
        puissances_opt = f"{optimum['puissance_souscrite_kva'][0]:.0f} kVA"
        puissances_detail_opt = f"""
    - **Puissance souscrite** : **{optimum['puissance_souscrite_kva'][0]:.0f} kVA** (mono-puissance)
    """

    # Optimums par FTA
    optimums_par_fta = (
        resultats
        .group_by(['pdl', 'formule_tarifaire_acheminement'])
        .agg([
            pl.col('turpe_total_eur').min().alias('cout_min_eur'),
            pl.col('puissance_souscrite_kva').filter(
                pl.col('turpe_total_eur') == pl.col('turpe_total_eur').min()
            ).first().alias('puissance_opt'),
        ])
        .sort('cout_min_eur')
    )

    mo.md(f"""
    ## 🏆 Recommandation optimale

    ### 📊 Comparaison Actuel vs Optimum

    | | **Configuration actuelle** | **Optimum recommandé** | **Gain** |
    |---|:---:|:---:|:---:|
    | **Formule tarifaire** | {fta_actuel_val} | {fta_opt} | - |
    | **Puissance(s)** | {puissances_actuel} | {puissances_opt} | - |
    | **Part fixe** | {cout_actuel['turpe_fixe_eur'][0]:,.2f} € | {optimum['turpe_fixe_eur'][0]:,.2f} € | {cout_actuel['turpe_fixe_eur'][0] - optimum['turpe_fixe_eur'][0]:,.2f} € |
    | **Part variable** | {cout_actuel['turpe_variable_eur'][0]:,.2f} € | {optimum['turpe_variable_eur'][0]:,.2f} € | {cout_actuel['turpe_variable_eur'][0] - optimum['turpe_variable_eur'][0]:,.2f} € |
    | **📈 COÛT TOTAL** | **{cout_actuel['turpe_total_eur'][0]:,.2f} €/an** | **{optimum['turpe_total_eur'][0]:,.2f} €/an** | **🎉 {economie_annuelle:,.2f} € ({economie_pct:.1f}%)** |

    ---

    **Détails de la configuration optimale :**
    - **PDL** : `{optimum['pdl'][0]}`
    {puissances_detail_opt}
    - **Formule tarifaire** : **{fta_opt}**

    ---

    ### 📊 Comparaison par formule tarifaire

    {optimums_par_fta.to_pandas().to_markdown(index=False)}
    """)
    return


@app.cell(hide_code=True)
def _(cout_actuel, resultats):
    # Graphique interactif avec marqueur pour le scénario actuel
    import altair as alt

    # Filtrer sur le premier PDL pour la visualisation
    pdl_unique = resultats['pdl'][0]
    df_plot = resultats.filter(pl.col('pdl') == pdl_unique)

    # Exclure les colonnes de dates (Altair ne supporte pas les timezones non-UTC)
    colonnes_sans_dates = [col for col in df_plot.columns if col not in ['debut', 'fin', 'date_debut', 'date_fin']]
    df_plot_clean = df_plot.select(colonnes_sans_dates)

    # Préparer le marqueur pour le scénario actuel
    import pandas as pd
    point_actuel_pd = pd.DataFrame({
        'puissance': [cout_actuel['puissance_souscrite_kva'][0]],
        'cout': [cout_actuel['turpe_total_eur'][0]],
        'label': ['Configuration actuelle']
    })

    # Graphique principal (scénarios d'optimisation)
    chart = alt.Chart(df_plot_clean.to_pandas()).mark_line(point=True).encode(
        x=alt.X('puissance_souscrite_kva:Q', title='Puissance souscrite max (kVA)'),
        y=alt.Y('turpe_total_eur:Q', title='Coût annuel TURPE (€/an)', scale=alt.Scale(zero=False)),
        color=alt.Color('formule_tarifaire_acheminement:N', title='Formule tarifaire'),
        tooltip=[
            alt.Tooltip('puissance_hph_kva:Q', title='P HPH (kVA)'),
            alt.Tooltip('puissance_hch_kva:Q', title='P HCH (kVA)'),
            alt.Tooltip('puissance_hpb_kva:Q', title='P HPB (kVA)'),
            alt.Tooltip('puissance_hcb_kva:Q', title='P HCB (kVA)'),
            alt.Tooltip('formule_tarifaire_acheminement:N', title='FTA'),
            alt.Tooltip('turpe_fixe_eur:Q', title='Part fixe (€)', format='.2f'),
            alt.Tooltip('turpe_variable_eur:Q', title='Part variable (€)', format='.2f'),
            alt.Tooltip('turpe_total_eur:Q', title='Total (€)', format='.2f'),
        ]
    ).properties(
        width=800,
        height=500,
        title=f"Coût TURPE vs Puissance souscrite max (HCB) - PDL {pdl_unique}"
    )

    # Marqueur rouge pour la configuration actuelle
    marqueur_actuel = alt.Chart(point_actuel_pd).mark_point(
        size=300,
        shape='diamond',
        color='red',
        filled=True,
        opacity=0.8
    ).encode(
        x=alt.X('puissance:Q'),
        y=alt.Y('cout:Q'),
        tooltip=[alt.Tooltip('label:N', title='Configuration')]
    )

    # Label pour le marqueur
    label_actuel = alt.Chart(point_actuel_pd).mark_text(
        align='left',
        dx=10,
        dy=-10,
        fontSize=15,
        fontWeight='bold',
        color='red'
    ).encode(
        x=alt.X('puissance:Q'),
        y=alt.Y('cout:Q'),
        text=alt.value('⬥ Actuel')
    )

    # Superposer les couches
    final_chart = (chart + label_actuel).interactive()

    _note_explicative = mo.md("""
    **Note sur le graphique** :
    - **⬥ Point rouge** : Configuration actuelle
    - **BTINF** (< 36 kVA) : mono-puissance, l'axe X représente la puissance unique souscrite
    - **BTSUP** (≥ 36 kVA) : multi-cadrans, l'axe X représente la puissance max (HCB)
    - Pour BTSUP, les 4 puissances par cadran (HPH ≤ HCH ≤ HPB ≤ HCB) sont visibles dans le tooltip
    - Passez la souris sur les points pour voir le détail complet de chaque configuration
    """)

    mo.vstack([mo.ui.altair_chart(final_chart), _note_explicative])
    return


@app.cell(hide_code=True)
def _(resultats):
    # Export Excel - Retirer les timezones pour compatibilité xlsxwriter
    excel_buffer = io.BytesIO()

    # Créer une copie sans timezone pour l'export
    resultats_excel = resultats.with_columns([
        pl.col('debut').dt.convert_time_zone('UTC').dt.replace_time_zone(None).alias('debut'),
        pl.col('fin').dt.convert_time_zone('UTC').dt.replace_time_zone(None).alias('fin'),
    ])

    resultats_excel.write_excel(excel_buffer)
    excel_data = excel_buffer.getvalue()

    _download_button = mo.download(
        data=excel_data,
        filename="Optimisation_TURPE_electricore.xlsx",
        label="📥 Télécharger les résultats détaillés (Excel)",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    _download_button
    return


if __name__ == "__main__":
    app.run()
