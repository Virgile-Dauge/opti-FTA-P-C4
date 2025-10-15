import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")

async with app.setup(hide_code=True):
    # Initialization code that runs before all other cells

    # Installation des dépendances pour WASM (Pyodide)
    import sys
    if "pyodide" in sys.modules:
        import micropip
        await micropip.install("polars")
        await micropip.install("pyarrow")
        await micropip.install("xlsxwriter")
        # electricore 1.2.0+ avec core minimal compatible WASM
        await micropip.install("electricore==1.3.4")

    # Imports standards
    import marimo as mo
    import polars as pl
    from pathlib import Path
    from datetime import datetime, time
    import io
    import altair as alt

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


@app.cell
def _(cdc):
    cdc
    return


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


@app.cell(hide_code=True)
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
def _(
    expr_cadran,
    expr_pas_heures,
    expr_pmax,
    expr_volume,
    file_upload,
    plages_hc,
):
    mo.stop(not file_upload.value, mo.md("⚠️ Veuillez uploader un fichier CSV"))

    # Pipeline EAGER - lecture directe depuis mémoire (temporaire avec toutes les colonnes)
    _cdc_temp = (
        pl.read_csv(io.BytesIO(file_upload.contents()), separator=';')
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
            expr_pmax().alias('pmax'),
            expr_cadran(plages_hc).alias('cadran')
        ])
    )

    # Extraire le pas en heures (constante)
    pas_heures = _cdc_temp.select('pas_heures').limit(1).item()

    # Calculer dates et pmax_moyenne par PDL
    dates_et_pmax_par_pdl = (
        _cdc_temp
        .group_by('Identifiant PRM')
        .agg([
            pl.col('Horodate').min().alias('date_debut'),
            pl.col('Horodate').max().alias('date_fin'),
            pl.col('pmax').max().alias('pmax_moyenne_kva'),
        ])
    )

    # Agrégation des énergies et pmax par PDL et cadran
    _energies_par_cadran = (
        _cdc_temp
        .group_by(['Identifiant PRM', 'cadran'])
        .agg([
            pl.col('volume').sum().alias('energie_kwh'),
            pl.col('pmax').max().alias('pmax_cadran_kva'),
        ])
    )

    # Pivots
    _energies_pivot = _energies_par_cadran.pivot(
        on='cadran',
        index='Identifiant PRM',
        values='energie_kwh',
    )

    _pmax_pivot = _energies_par_cadran.pivot(
        on='cadran',
        index='Identifiant PRM',
        values='pmax_cadran_kva',
    )

    # Joindre tout
    consos_agregees = (
        _energies_pivot
        .join(dates_et_pmax_par_pdl, on='Identifiant PRM', how='left')
        .join(
            _pmax_pivot.rename({
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
        ])
    )

    # DataFrame ultra-optimisé : agrégation par combinaisons uniques de (PRM, cadran, pmax)
    # Réduction ~99.7% en mémoire : de ~105k lignes à ~250 lignes par PDL
    cdc = (
        _cdc_temp
        .group_by(['Identifiant PRM', 'cadran', 'pmax'])
        .agg([
            (pl.len() * pas_heures).alias('duree_h')
        ])
        # Trier par pmax décroissant pour calculer le cumul de dépassement
        .sort(['Identifiant PRM', 'cadran', 'pmax'], descending=[False, False, True])
        .with_columns([
            # Cumul des heures = nombre d'heures où cette puissance est dépassée
            pl.col('duree_h')
              .cum_sum()
              .over(['Identifiant PRM', 'cadran'])
              .alias('duree_depassement_h')
        ])
    )
    return cdc, consos_agregees


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

    def expr_pmax() -> pl.Expr:
        """
        Expression Polars pour estimer la Pmax en kVA.

        volume = Valeur (kW) × coef

        Returns:
            Expression Polars du volume en kWh
        """
        return (pl.col('Valeur') * 1.10).round(3)

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
    return expr_cadran, expr_pas_heures, expr_pmax, expr_volume


@app.cell(hide_code=True)
def _(consos_agregees):
    _nb_pdl = len(consos_agregees)
    _energie_totale = (
        consos_agregees['energie_hph_kwh'].sum() +
        consos_agregees['energie_hch_kwh'].sum() +
        consos_agregees['energie_hpb_kwh'].sum() +
        consos_agregees['energie_hcb_kwh'].sum()
    )

    mo.md(f"""
    ## 🔄 Agrégation par PDL et pivotage des cadrans

    ✅ **Agrégation terminée**

    - Nombre de PDL : {_nb_pdl}
    - Énergie totale : {_energie_totale:,.0f} kWh
    """)
    return


@app.cell
def _(consos_agregees):
    consos_agregees
    return


@app.cell
def _():
    mo.md(r"""## 🎯 Génération des scénarios d'optimisation""")
    return


@app.function(hide_code=True)
def generer_scenarios_reduction_proportionnelle(
    consos_agregees: pl.DataFrame,
    config_actuelle: dict = None
) -> pl.DataFrame:
    """
    Génère les scénarios multi-cadrans par réduction proportionnelle simultanée.

    Principe :
    - Part de (pmax_hph, pmax_hch, pmax_hpb, pmax_hcb) × 1.15 arrondi
    - Applique la contrainte P_hph ≤ P_hch ≤ P_hpb ≤ P_hcb
    - Réduit toutes les puissances de 1 kVA simultanément jusqu'à ce que le min atteigne 36

    Args:
        consos_agregees: DataFrame avec les consommations agrégées
        config_actuelle: Dict optionnel avec les clés:
            - 'fta': formule tarifaire actuelle (ex: 'BTSUPCU')
            - 'p_hph', 'p_hch', 'p_hpb', 'p_hcb': puissances actuelles par cadran

    Hypothèse : Le profil de charge est similaire entre cadrans (seule l'amplitude diffère)
    """
    from math import ceil

    scenarios_list = []

    for row in consos_agregees.iter_rows(named=True):
        # Étape 1 : Calculer les puissances de base
        p_hph_base = int(ceil(row['pmax_hph_kva']))
        p_hch_base = int(ceil(row['pmax_hch_kva']))
        p_hpb_base = int(ceil(row['pmax_hpb_kva']))
        p_hcb_base = int(ceil(row['pmax_hcb_kva']))

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

    # Marquer le scénario actuel si fourni
    if config_actuelle is not None:
        df_scenarios = df_scenarios.with_columns([
            (
                (pl.col('formule_tarifaire_acheminement') == config_actuelle['fta']) &
                (pl.col('puissance_hph_kva') == config_actuelle['p_hph']) &
                (pl.col('puissance_hch_kva') == config_actuelle['p_hch']) &
                (pl.col('puissance_hpb_kva') == config_actuelle['p_hpb']) &
                (pl.col('puissance_hcb_kva') == config_actuelle['p_hcb'])
            ).alias('est_scenario_actuel')
        ])
    else:
        df_scenarios = df_scenarios.with_columns([
            pl.lit(False).alias('est_scenario_actuel')
        ])

    return df_scenarios


@app.cell(hide_code=True)
def _(
    cdc,
    consos_agregees,
    fta_actuel,
    puissance_actuelle_hcb,
    puissance_actuelle_hch,
    puissance_actuelle_hpb,
    puissance_actuelle_hph,
    puissance_actuelle_mono,
):
    # Génération du scénario actuel pour comparaison

    # Sélectionner les colonnes nécessaires pour le calcul de dépassement
    #_cdc_actuel = cdc.select(['Valeur', 'pas_heures', 'cadran'])

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
        cdc,
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
            # Marquer comme scénario actuel
            pl.lit(True).alias('est_scenario_actuel'),
        ])
        .select([
            'pdl', 'energie_hph_kwh', 'energie_hch_kwh', 'energie_hpb_kwh', 'energie_hcb_kwh',
            'date_debut', 'date_fin', 'nb_jours',
            'puissance_souscrite_kva', 'formule_tarifaire_acheminement', 'duree_depassement_h',
            'puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva',
            'est_scenario_actuel'
        ])
    )
    return (scenario_actuel,)


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _(
    cdc,
    consos_agregees,
    fta_actuel,
    plage_puissance,
    puissance_actuelle_hcb,
    puissance_actuelle_hch,
    puissance_actuelle_hpb,
    puissance_actuelle_hph,
    puissance_actuelle_mono,
):
    # Génération des scénarios multi-cadrans par réduction proportionnelle

    _P_min, _P_max = plage_puissance.value

    # Mode multi-cadrans: réduction proportionnelle simultanée

    # Étape 1: Scénarios BTINF mono-puissance (< 36 kVA) si nécessaire
    _scenarios_btinf = None
    if _P_min < 36:
        _puissances_btinf = list(range(_P_min, min(36, _P_max + 1)))

        # Identifier le scénario actuel si c'est BTINF
        _is_btinf_actuel = fta_actuel.value in ['BTINFCU4', 'BTINFMU4', 'BTINFLU']

        _scenarios_btinf = (
            consos_agregees
            .select(['pdl', 'energie_hph_kwh', 'energie_hch_kwh',
                     'energie_hpb_kwh', 'energie_hcb_kwh', 'pmax_moyenne_kva'])
            .with_columns([
                pl.lit(datetime(2025, 8, 1)).dt.replace_time_zone('Europe/Paris').alias('date_debut'),
                pl.lit(datetime(2026, 7, 31)).dt.replace_time_zone('Europe/Paris').alias('date_fin'),
                pl.lit(365).alias('nb_jours'),
                pl.lit(_puissances_btinf).alias('puissance_souscrite_kva')
            ])
            .explode('puissance_souscrite_kva')
            .with_columns([
                pl.lit(['BTINFCU4', 'BTINFMU4', 'BTINFLU']).alias('formule_tarifaire_acheminement')
            ])
            .explode('formule_tarifaire_acheminement')
        )

        # Marquer le scénario actuel si applicable
        if _is_btinf_actuel:
            _puissance_actuel = float(puissance_actuelle_mono.value)
            _fta_actuel = fta_actuel.value
            _scenarios_btinf = _scenarios_btinf.with_columns([
                (
                    (pl.col('puissance_souscrite_kva') == _puissance_actuel) &
                    (pl.col('formule_tarifaire_acheminement') == _fta_actuel)
                ).alias('est_scenario_actuel')
            ])
        else:
            _scenarios_btinf = _scenarios_btinf.with_columns([
                pl.lit(False).alias('est_scenario_actuel')
            ])

        _scenarios_btinf = (
            _scenarios_btinf
            .filter(
                # Garder soit les scénarios valides, soit le scénario actuel
                (pl.col('puissance_souscrite_kva') >= pl.col('pmax_moyenne_kva')) |
                pl.col('est_scenario_actuel')
            )
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
    # Identifier le scénario actuel si c'est BTSUP
    _is_btsup_actuel = fta_actuel.value in ['BTSUPCU', 'BTSUPLU']
    _config_actuelle_btsup = None
    if _is_btsup_actuel:
        _config_actuelle_btsup = {
            'fta': fta_actuel.value,
            'p_hph': float(puissance_actuelle_hph.value),
            'p_hch': float(puissance_actuelle_hch.value),
            'p_hpb': float(puissance_actuelle_hpb.value),
            'p_hcb': float(puissance_actuelle_hcb.value),
        }

    _scenarios_btsup = generer_scenarios_reduction_proportionnelle(
        consos_agregees,
        config_actuelle=_config_actuelle_btsup
    )

    # Calculer dépassements pour BTSUP
    _scenarios_btsup = _scenarios_btsup.with_columns([
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
    _colonnes_ordre = [
        'pdl', 'energie_hph_kwh', 'energie_hch_kwh', 'energie_hpb_kwh', 'energie_hcb_kwh',
        'date_debut', 'date_fin', 'nb_jours',
        'puissance_souscrite_kva', 'formule_tarifaire_acheminement', 'duree_depassement_h',
        'puissance_hph_kva', 'puissance_hch_kva', 'puissance_hpb_kva', 'puissance_hcb_kva',
        'est_scenario_actuel'
    ]

    # Ajouter pmax_moyenne_kva si nécessaire pour BTINF
    if 'pmax_moyenne_kva' in _scenarios_btsup.columns:
        _scenarios_btsup = _scenarios_btsup.select(_colonnes_ordre + ['pmax_moyenne_kva'])
    else:
        _scenarios_btsup = _scenarios_btsup.select(_colonnes_ordre)

    # Concaténer BTINF et BTSUP
    if _scenarios_btinf is not None:
        _colonnes_communes = [col for col in _colonnes_ordre if col in _scenarios_btinf.columns]
        _scenarios_btinf = _scenarios_btinf.select(_colonnes_communes)
        _scenarios_btsup = _scenarios_btsup.select(_colonnes_communes)
        scenarios = pl.concat([_scenarios_btinf, _scenarios_btsup])
    else:
        scenarios = _scenarios_btsup

    _nb_scenarios_btsup = len(_scenarios_btsup)
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
        cdc: DataFrame agrégé avec colonnes 'pmax' (kVA), 'cadran', 'duree_h' (heures)
        puissance_hph_kva, puissance_hch_kva, puissance_hpb_kva, puissance_hcb_kva:
            Puissances souscrites par cadran (kVA)

    Returns:
        Durée totale de dépassement en heures (somme sur tous les cadrans)
    """
    # Mapping cadran → seuil (plus élégant que when/then)
    seuils_map = {
        'HPH': puissance_hph_kva,
        'HCH': puissance_hch_kva,
        'HPB': puissance_hpb_kva,
        'HCB': puissance_hcb_kva,
    }

    return (
        cdc
        .with_columns([
            pl.col('cadran').replace(seuils_map).cast(pl.Float64).alias('puissance_seuil')
        ])
        # Ne compter que les dépassements (pmax > seuil du cadran)
        .filter(pl.col('pmax') > pl.col('puissance_seuil'))
        # Sommer directement les durées pré-agrégées
        .select(pl.col('duree_h').sum())
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
    print(f"🔍 Chargement des règles TURPE...")
    _regles_turpe = load_turpe_rules()
    print(f"✅ Règles TURPE chargées")

    # Concaténer scénario actuel avec les scénarios d'optimisation
    print(f"🔍 Concatenation: {len(scenario_actuel)} + {len(scenarios)} scénarios")
    _tous_scenarios = pl.concat([scenario_actuel, scenarios])
    print(f"✅ Total: {len(_tous_scenarios)} scénarios")

    # Calcul TURPE via electricore sur tous les scénarios
    print(f"🔍 Préparation des données...")
    _prepared = (
        _tous_scenarios
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
    )
    print(f"✅ Données préparées")

    print(f"🔍 Calcul TURPE fixe...")
    if "pyodide" in sys.modules:
        print(f"   (Mode WASM - ceci peut échouer avec 'Cannot allocate memory')")
    _with_fixe = _prepared.pipe(ajouter_turpe_fixe, regles=_regles_turpe)
    print(f"✅ TURPE fixe calculé")

    print(f"🔍 Calcul TURPE variable...")
    _with_variable = _with_fixe.pipe(ajouter_turpe_variable, regles=_regles_turpe)
    print(f"✅ TURPE variable calculé")

    print(f"🔍 Calcul total et collect()...")

    import gc
    gc.collect()
    _resultats_tous = (
        _with_variable
        .with_columns([
            (pl.col('turpe_fixe_eur') + pl.col('turpe_variable_eur')).alias('turpe_total_eur')
        ])
        # Optimisation WASM : convertir en Categorical APRÈS les calculs (évite problème de merge)
        .with_columns([
            pl.col('pdl').cast(pl.String).cast(pl.Categorical),
            pl.col('formule_tarifaire_acheminement').cast(pl.Categorical)
        ])
        # Sélectionner uniquement les colonnes nécessaires pour réduire la mémoire
        .select([
            'pdl',
            'formule_tarifaire_acheminement',
            'puissance_souscrite_kva',
            'puissance_hph_kva',
            'puissance_hch_kva',
            'puissance_hpb_kva',
            'puissance_hcb_kva',
            'turpe_fixe_eur',
            'turpe_variable_eur',
            'turpe_total_eur',
            'est_scenario_actuel'
        ])
        .collect()
    )
    print(f"✅ Collect terminé")

    # Séparer scénario actuel vs résultats d'optimisation
    cout_actuel = _resultats_tous.filter(pl.col('est_scenario_actuel') == True)
    resultats = _resultats_tous.filter(pl.col('est_scenario_actuel') == False)

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
    # Graphique interactif avec marqueurs pour actuel et optimal
    # Filtrer sur le premier PDL pour la visualisation
    pdl_unique = resultats['pdl'][0]
    df_plot = (
        resultats
        .filter(pl.col('pdl') == pdl_unique)
        # Trier par FTA puis par puissance pour que les lignes se tracent correctement
        .sort(['formule_tarifaire_acheminement', 'puissance_souscrite_kva'])
    )

    # Trouver l'optimum
    idx_opt_graph = df_plot['turpe_total_eur'].arg_min()
    optimum_graph = df_plot[idx_opt_graph]

    # Exclure les colonnes de dates et est_scenario_actuel (Altair ne supporte pas les timezones non-UTC)
    colonnes_sans_dates = [col for col in df_plot.columns if col not in ['debut', 'fin', 'date_debut', 'date_fin', 'est_scenario_actuel']]
    df_plot_clean = df_plot.select(colonnes_sans_dates)

    # S'assurer que les colonnes numériques sont bien typées
    df_plot_clean = df_plot_clean.with_columns([
        pl.col('puissance_souscrite_kva').cast(pl.Int64),
        pl.col('turpe_total_eur').cast(pl.Float64),
        pl.col('turpe_fixe_eur').cast(pl.Float64),
        pl.col('turpe_variable_eur').cast(pl.Float64),
    ])

    # Convertir en pandas pour Altair (plus de compatibilité qu'avec to_dicts)
    data_plot = df_plot_clean.to_pandas()

    # Préparer les marqueurs (utiliser les MÊMES noms de colonnes que data_plot)
    import pandas as pd
    points_speciaux = pd.DataFrame([
        {
            'puissance_souscrite_kva': cout_actuel['puissance_souscrite_kva'][0],
            'turpe_total_eur': cout_actuel['turpe_total_eur'][0],
            'label': 'Actuel',
            'type': 'actuel'
        },
        {
            'puissance_souscrite_kva': optimum_graph['puissance_souscrite_kva'][0],
            'turpe_total_eur': optimum_graph['turpe_total_eur'][0],
            'label': 'Optimal',
            'type': 'optimal'
        }
    ])

    # Graphique principal : lignes + points en une seule couche
    chart = alt.Chart(data_plot).mark_line(point=True).encode(
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

    # Marqueurs pour actuel et optimal
    marqueurs = alt.Chart(points_speciaux).mark_point(
        size=300,
        shape='diamond',
        filled=True,
        opacity=0.8
    ).encode(
        x='puissance_souscrite_kva:Q',
        y='turpe_total_eur:Q',
        color=alt.Color('type:N',
            scale=alt.Scale(domain=['actuel', 'optimal'], range=['red', 'green']),
            legend=None
        ),
        tooltip=['label:N']
    )

    # Labels pour les marqueurs
    labels = alt.Chart(points_speciaux).mark_text(
        align='left',
        dx=10,
        dy=-10,
        fontSize=15,
        fontWeight='bold'
    ).encode(
        x='puissance_souscrite_kva:Q',
        y='turpe_total_eur:Q',
        text='label:N',
        color=alt.Color('type:N',
            scale=alt.Scale(domain=['actuel', 'optimal'], range=['red', 'green']),
            legend=None
        )
    )

    # Superposer toutes les couches avec l'opérateur +
    final_chart = (
        chart + marqueurs + labels
    ).resolve_scale(
        color='independent'
    ).interactive()

    _note_explicative = mo.md("""
    **Note sur le graphique** :
    - **⬥ Point rouge (Actuel)** : Configuration actuelle
    - **⬥ Point vert (Optimal)** : Configuration optimale recommandée
    - **BTINF** (< 36 kVA) : mono-puissance, l'axe X représente la puissance unique souscrite
    - **BTSUP** (≥ 36 kVA) : multi-cadrans, l'axe X représente la puissance max (HCB)
    - Pour BTSUP, les 4 puissances par cadran (HPH ≤ HCH ≤ HPB ≤ HCB) sont visibles dans le tooltip
    - Passez la souris sur les points pour voir le détail complet de chaque configuration
    """)

    mo.vstack([mo.ui.altair_chart(final_chart), _note_explicative])
    return


@app.cell
def _():
    mo.md(r"""## 📈 Analyse du profil de charge""")
    return


@app.cell(hide_code=True)
def _(cdc):
    # Courbe de monotone (load duration curve) par cadran
    # Utilise directement la colonne duree_depassement_h calculée dans cdc
    df_monotone_final = (
        cdc
        .select(['cadran', 'pmax', 'duree_depassement_h'])
        .rename({'duree_depassement_h': 'duree_cumulee_h'})
        .to_pandas()
    )

    # Graphique de monotone
    monotone_chart = alt.Chart(df_monotone_final).mark_line(point=False).encode(
        x=alt.X('duree_cumulee_h:Q',
                title='Durée de dépassement (heures/an)',
                scale=alt.Scale(zero=True)),
        y=alt.Y('pmax:Q',
                title='Puissance (kVA)',
                scale=alt.Scale(zero=False)),
        color=alt.Color('cadran:N',
                       title='Cadran tarifaire',
                       scale=alt.Scale(
                           domain=['HPH', 'HCH', 'HPB', 'HCB'],
                           range=['#e74c3c', '#e67e22', '#3498db', '#2ecc71']
                       )),
        tooltip=[
            alt.Tooltip('cadran:N', title='Cadran'),
            alt.Tooltip('pmax:Q', title='Puissance (kVA)', format='.1f'),
            alt.Tooltip('duree_cumulee_h:Q', title='Heures de dépassement', format=',.0f')
        ]
    ).properties(
        width=800,
        height=500,
        title={
            "text": "Courbe de monotone - Profil de puissance par cadran tarifaire",
            "subtitle": "Cette courbe montre la durée pendant laquelle chaque niveau de puissance est dépassé"
        }
    ).interactive()

    _note_monotone = mo.md("""
    **Lecture du graphique** :
    - **Axe horizontal** : durée cumulée dans l'année (heures)
    - **Axe vertical** : puissance en kVA
    - Chaque point (x, y) signifie : "la puissance y est dépassée pendant x heures dans l'année"
    - Plus la courbe est haute à droite, plus la consommation est stable
    - Une chute rapide à gauche indique des pics de puissance courts
    - **HPH** (rouge) : Heures Pleines Hiver
    - **HCH** (orange) : Heures Creuses Hiver
    - **HPB** (bleu) : Heures Pleines Basse saison
    - **HCB** (vert) : Heures Creuses Basse saison
    """)

    mo.vstack([mo.ui.altair_chart(monotone_chart), _note_monotone])
    return


@app.cell(hide_code=True)
def _(cdc):
    # Histogramme durée cumulée par tranche de puissance et cadran

    # Agréger durée par puissance arrondie et cadran
    df_histo = (
        cdc
        .with_columns([
            # Arrondir pmax à l'entier le plus proche pour réduire la granularité
            pl.col('pmax').round(0).alias('pmax_arrondi')
        ])
        .group_by(['cadran', 'pmax_arrondi'])
        .agg([
            pl.col('duree_h').sum().alias('duree_totale_h')
        ])
        .sort(['cadran', 'pmax_arrondi'])
        .to_pandas()
    )

    # Créer l'histogramme empilé
    histo_chart = alt.Chart(df_histo).mark_bar().encode(
        x=alt.X('pmax_arrondi:Q',
                title='Puissance (kVA)',
                bin=alt.Bin(maxbins=50)),
        y=alt.Y('sum(duree_totale_h):Q',
                title='Durée totale (heures/an)',
                stack='zero'),
        color=alt.Color('cadran:N',
                       title='Cadran tarifaire',
                       scale=alt.Scale(
                           domain=['HPH', 'HCH', 'HPB', 'HCB'],
                           range=['#e74c3c', '#e67e22', '#3498db', '#2ecc71']
                       )),
        tooltip=[
            alt.Tooltip('cadran:N', title='Cadran'),
            alt.Tooltip('pmax_arrondi:Q', title='Puissance (kVA)', format='.0f'),
            alt.Tooltip('sum(duree_totale_h):Q', title='Durée (h)', format=',.1f')
        ]
    ).properties(
        width=800,
        height=400,
        title="Distribution de la durée par niveau de puissance et cadran"
    ).interactive()

    _note_histo = mo.md("""
    **Lecture du graphique** :
    - Chaque barre représente le temps passé à un niveau de puissance donné
    - Les couleurs empilées montrent la répartition entre cadrans tarifaires
    - Les pics indiquent les niveaux de puissance les plus fréquents
    - Une distribution étalée indique une consommation variable
    """)

    mo.vstack([mo.ui.altair_chart(histo_chart), _note_histo])
    return


@app.cell
def _():
    mo.md(r"""### 🎯 Analyse interactive des dépassements par seuil""")
    return


@app.cell(hide_code=True)
def _(cdc):
    # Slider pour choisir un seuil de puissance
    seuil_puissance = mo.ui.slider(
        start=int(cdc['pmax'].min()),
        stop=int(cdc['pmax'].max()),
        value=40,
        step=1,
        label="Seuil de puissance souscrite (kVA)",
        show_value=True
    )
    seuil_puissance
    return (seuil_puissance,)


@app.cell(hide_code=True)
def _(cdc, seuil_puissance):
    # Calculer les heures de dépassement pour le seuil choisi par cadran
    _seuil = seuil_puissance.value

    # Pour chaque cadran, trouver la durée de dépassement au seuil choisi
    # On prend la valeur de duree_depassement_h pour la puissance la plus proche du seuil
    depassements_par_cadran = (
        cdc
        .filter(pl.col('pmax') >= _seuil)
        .group_by('cadran')
        .agg([
            pl.col('duree_depassement_h').max().alias('heures_depassement')
        ])
        .to_pandas()
    )

    # Graphique en barres
    depassement_chart = alt.Chart(depassements_par_cadran).mark_bar().encode(
        x=alt.X('cadran:N',
                title='Cadran tarifaire',
                sort=['HPH', 'HCH', 'HPB', 'HCB']),
        y=alt.Y('heures_depassement:Q',
                title='Heures de dépassement/an'),
        color=alt.Color('cadran:N',
                       title='Cadran',
                       scale=alt.Scale(
                           domain=['HPH', 'HCH', 'HPB', 'HCB'],
                           range=['#e74c3c', '#e67e22', '#3498db', '#2ecc71']
                       ),
                       legend=None),
        tooltip=[
            alt.Tooltip('cadran:N', title='Cadran'),
            alt.Tooltip('heures_depassement:Q', title='Heures/an', format=',.0f')
        ]
    ).properties(
        width=600,
        height=400,
        title=f"Heures de dépassement pour un seuil de {_seuil} kVA"
    )

    # Calcul du total
    _total_depassement = depassements_par_cadran['heures_depassement'].sum()

    _note_depassement = mo.md(f"""
    **Interprétation** :
    - Pour une puissance souscrite de **{_seuil} kVA** dans chaque cadran
    - **Total annuel** : {_total_depassement:,.0f} heures de dépassement
    - Les dépassements entraînent des pénalités en tarif C4
    - Ajustez le slider pour trouver le bon compromis coût fixe / pénalités
    """)

    mo.vstack([mo.ui.altair_chart(depassement_chart), _note_depassement])
    return


if __name__ == "__main__":
    app.run()
