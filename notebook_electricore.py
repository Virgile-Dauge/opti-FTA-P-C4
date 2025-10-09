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
        await micropip.install("electricore==1.1.0")

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


@app.cell
def _():
    mo.md(r"""## 📥 Traitement de la courbe de charge""")
    return


@app.cell(hide_code=True)
def _(file_upload):
    # Chargement des données brutes
    mo.stop(not file_upload.value, mo.md("⚠️ Veuillez uploader un fichier CSV pour commencer l'analyse"))

    csv_content = file_upload.contents()
    _cdc_tmp = pl.read_csv(io.BytesIO(csv_content), separator=';')

    # Vérification colonnes
    colonnes_requises = ['Horodate', 'Grandeur physique', 'Valeur', 'Pas']
    colonnes_manquantes = [col for col in colonnes_requises if col not in _cdc_tmp.columns]

    mo.stop(colonnes_manquantes, mo.md(f"❌ Colonnes manquantes : {', '.join(colonnes_manquantes)}"))

    # Filtrer PA et convertir uniquement les données de base
    cdc_brut = (
        _cdc_tmp
        .filter(pl.col('Grandeur physique') == 'PA')
        .with_columns([
            pl.col('Horodate').str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S'),
            (pl.col('Valeur') / 1000.0).alias('Valeur'),  # Watts -> kW
        ])
        .select(['Horodate', 'Valeur', 'Pas', 'Identifiant PRM'])
    )

    mo.stop(cdc_brut.is_empty(), mo.md("❌ Aucune donnée de Puissance Active (PA) trouvée"))

    mo.md(f"""
    ✅ **Données brutes chargées**

    - Nombre de mesures : {len(cdc_brut):,}
    - Période : {cdc_brut['Horodate'].min()} → {cdc_brut['Horodate'].max()}
    - Puissance max : {cdc_brut['Valeur'].max():.2f} kW
    """)
    return (cdc_brut,)


@app.cell(hide_code=True)
def _(cdc_brut):
    # Affichage des PRMs
    _prms = cdc_brut['Identifiant PRM'].unique().sort()
    _nb_prms = len(_prms)

    if _nb_prms == 1:
        _msg = mo.md(f"ℹ️ **PRM identifié** : `{_prms[0]}`")
    else:
        _prms_list = '\n'.join([f"- `{prm}`" for prm in _prms])
        _msg = mo.md(f"""
            ⚠️ **Attention : {_nb_prms} PRMs détectés dans le fichier**

            {_prms_list}

            Les analyses portent sur l'ensemble des données. Si vous souhaitez analyser un seul PRM,
            merci de filtrer le fichier CSV en amont.
        """)
    _msg
    return


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

    def enrichir_dataframe(df: pl.DataFrame, plages_hc: list[tuple[time, time]]) -> pl.DataFrame:
        """
        Enrichit le DataFrame avec les colonnes pas_heures, volume et cadran.

        Args:
            df: DataFrame avec colonnes 'Horodate', 'Valeur', 'Pas'
            plages_hc: Liste de tuples (heure_debut, heure_fin) pour les HC

        Returns:
            DataFrame enrichi avec colonnes supplémentaires
        """
        return (
            df
            .with_columns([
                expr_pas_heures().alias('pas_heures')
            ])
            .with_columns([
                expr_volume().alias('volume'),
                expr_cadran(plages_hc).alias('cadran')
            ])
        )
    return (enrichir_dataframe,)


@app.cell(hide_code=True)
def _(cdc_brut, enrichir_dataframe, plages_hc):
    # Enrichissement des données avec cadrans tarifaires
    cdc = enrichir_dataframe(cdc_brut, plages_hc)

    duree_jours = (cdc['Horodate'].max() - cdc['Horodate'].min()).days
    warning = f"\n⚠️ Seulement {duree_jours} jours de données (recommandé : 365 jours)" if duree_jours < 365 else ""

    # Extraire le pas de temps
    pas_exemple = cdc['Pas'][0]
    pas_uniques = cdc['Pas'].n_unique()
    warning_pas = f"\n⚠️ Attention : {pas_uniques} pas de temps différents détectés" if pas_uniques > 1 else ""

    # Statistiques par cadran
    _stats_cadrans = cdc.group_by('cadran').agg([
        pl.col('volume').sum().alias('volume_total')
    ]).sort('cadran')

    _cadrans_str = "\n".join([
        f"     - {row['cadran']} : {row['volume_total']:.0f} kWh"
        for row in _stats_cadrans.iter_rows(named=True)
    ])

    mo.md(f"""
        ✅ **Données enrichies avec succès**

        - Pas de temps : {pas_exemple}{warning_pas}

        **Consommation par cadran tarifaire :**
        {_cadrans_str}
        {warning}
    """)
    return (cdc,)


@app.cell
def _(cdc):
    cdc
    return


@app.cell
def _():
    mo.md(r"""## 🔄 Agrégation par PDL et pivotage des cadrans""")
    return


@app.cell(hide_code=True)
def _(cdc):
    # Étape 1: Calculer les dates globales par PDL (AVANT le pivot)
    dates_pdl = (
        cdc
        .group_by('Identifiant PRM')
        .agg([
            pl.col('Horodate').min().alias('date_debut'),
            pl.col('Horodate').max().alias('date_fin'),
            pl.col('Valeur').max().alias('pmax'),
        ])
    )

    # Étape 2: Agrégation des énergies par PDL et cadran
    energies_par_cadran = (
        cdc
        .group_by(['Identifiant PRM', 'cadran'])
        .agg([
            pl.col('volume').sum().alias('energie_kwh'),
        ])
    )

    # Étape 3: Pivot pour avoir tous les cadrans sur une ligne par PDL
    consos_agregees = (
        energies_par_cadran
        .pivot(
            on='cadran',
            index='Identifiant PRM',
            values='energie_kwh',
        )
        # Joindre les dates globales
        .join(dates_pdl, on='Identifiant PRM', how='left')
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


@app.cell(hide_code=True)
def _(cdc, consos_agregees, plage_puissance):
    # Génération de tous les scénarios (puissances × FTA)

    P_min, P_max = plage_puissance.value
    puissances = list(range(P_min, P_max + 1))

    # Créer une dataframe avec toutes les puissances
    scenarios = (
        consos_agregees
        .select(['pdl', 'energie_hph_kwh', 'energie_hch_kwh',
                 'energie_hpb_kwh', 'energie_hcb_kwh', 'pmax'])
        .with_columns([
            # Dates projectives pour tous les scénarios (compatibilité TURPE rules)
            pl.lit(datetime(2025, 8, 1)).dt.replace_time_zone('Europe/Paris').alias('date_debut'),
            pl.lit(datetime(2026, 7, 31)).dt.replace_time_zone('Europe/Paris').alias('date_fin'),
            pl.lit(365).alias('nb_jours'),
            pl.lit(puissances).alias('puissance_souscrite_kva')
        ])
        .explode('puissance_souscrite_kva')
        .with_columns([
            pl.when(pl.col('puissance_souscrite_kva') < 36)
            .then(pl.lit(['BTINFCU4', 'BTINFMU4', 'BTINFLU']))
            .otherwise(pl.lit(['BTSUPCU', 'BTSUPLU']))
            .alias('formule_tarifaire_acheminement')
        ])
        .explode('formule_tarifaire_acheminement')
        .with_columns([
            # Calculer durée dépassement pour chaque ligne
            pl.struct(['puissance_souscrite_kva'])
            .map_elements(
                lambda row: calculer_duree_depassement_df(cdc, row['puissance_souscrite_kva']),
                return_dtype=pl.Float64
            )
            .alias('duree_depassement_h')
        ])
    )

    _nb_scenarios = len(scenarios)
    _nb_pdl = scenarios['pdl'].n_unique()

    mo.md(f"""
    ✅ **Scénarios générés**

    - Nombre de scénarios : {_nb_scenarios:,}
    - PDL : {_nb_pdl}
    - Puissances : {P_min} à {P_max} kVA
    - FTA testées : BTINFCU4, BTINFMU4, BTINFLU, (< 36 kVA) + BTSUPCU, BTSUPLU (≥ 36 kVA)
    """)
    return (scenarios,)


@app.function(hide_code=True)
# Fonction pour calculer la durée de dépassement par puissance
def calculer_duree_depassement_df(cdc: pl.DataFrame, puissance_kw: float) -> float:
    """
    Calcule la durée totale de dépassement en heures pour une puissance donnée.

    Args:
        cdc: DataFrame avec colonnes 'Valeur' (kW) et 'pas_heures'
        puissance_kw: Puissance souscrite en kW

    Returns:
        Durée de dépassement en heures
    """
    return (
        cdc
        .filter(pl.col('Valeur') > puissance_kw)
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
def _(scenarios):
    # Charger les règles TURPE une seule fois
    regles_turpe = load_turpe_rules()

    # Calcul TURPE via electricore
    # Préparer les données au format attendu par electricore
    resultats = (
        scenarios
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
            # Pour C4 : initialiser les 4 puissances souscrites par cadran
            # (identiques pour commencer, l'utilisateur peut optimiser ensuite)
            pl.col('puissance_souscrite_kva').alias('puissance_souscrite_hph_kva'),
            pl.col('puissance_souscrite_kva').alias('puissance_souscrite_hch_kva'),
            pl.col('puissance_souscrite_kva').alias('puissance_souscrite_hpb_kva'),
            pl.col('puissance_souscrite_kva').alias('puissance_souscrite_hcb_kva'),
        ])
        .lazy()
        .pipe(ajouter_turpe_fixe, regles=regles_turpe)
        .pipe(ajouter_turpe_variable, regles=regles_turpe)
        .with_columns([
            # Renommer pour cohérence (electricore utilise suffixe _eur)
            # pl.col('turpe_fixe_eur').alias('turpe_fixe'),
            # pl.col('turpe_variable_eur').alias('turpe_variable'),
            (pl.col('turpe_fixe_eur') + pl.col('turpe_variable_eur')).alias('turpe_total_eur')
        ])
        .collect()
    )

    _nb_resultats = len(resultats)
    _cout_min = resultats['turpe_total_eur'].min()
    _cout_max = resultats['turpe_total_eur'].max()

    mo.md(f"""
    ✅ **Calculs TURPE terminés**

    - Scénarios calculés : {_nb_resultats:,}
    - Coût min : {_cout_min:.2f} €/an
    - Coût max : {_cout_max:.2f} €/an
    """)
    return (resultats,)


@app.cell
def _(resultats):
    resultats
    return


@app.cell
def _():
    mo.md(r"""## 🎯 Résultats et recommandations""")
    return


@app.cell(hide_code=True)
def _(resultats):
    # Trouver l'optimum global (toutes FTA confondues)
    idx_opt = resultats['turpe_total_eur'].arg_min()
    optimum = resultats[idx_opt]

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

    **Meilleure configuration** :
    - **PDL** : `{optimum['pdl'][0]}`
    - **Puissance souscrite** : **{optimum['puissance_souscrite_kva'][0]:.0f} kVA**
    - **Formule tarifaire** : **{optimum['formule_tarifaire_acheminement'][0]}**
    - **Coût annuel TURPE** : **{optimum['turpe_total_eur'][0]:,.2f} €/an**
      - Part fixe : {optimum['turpe_fixe_eur'][0]:,.2f} €/an
      - Part variable : {optimum['turpe_variable_eur'][0]:,.2f} €/an

    ---

    ### 📊 Comparaison par formule tarifaire

    {optimums_par_fta.to_pandas().to_markdown(index=False)}
    """)
    return


@app.cell(hide_code=True)
def _(resultats):
    # Graphique interactif
    import altair as alt

    # Filtrer sur le premier PDL pour la visualisation
    pdl_unique = resultats['pdl'][0]
    df_plot = resultats.filter(pl.col('pdl') == pdl_unique)

    # Créer le graphique
    chart = alt.Chart(df_plot.to_pandas()).mark_line(point=True).encode(
        x=alt.X('puissance_souscrite_kva:Q', title='Puissance souscrite (kVA)'),
        y=alt.Y('turpe_total:Q', title='Coût annuel TURPE (€/an)', scale=alt.Scale(zero=False)),
        color=alt.Color('formule_tarifaire_acheminement:N', title='Formule tarifaire'),
        tooltip=[
            alt.Tooltip('puissance_souscrite_kva:Q', title='Puissance (kVA)'),
            alt.Tooltip('formule_tarifaire_acheminement:N', title='FTA'),
            alt.Tooltip('turpe_fixe:Q', title='Part fixe (€)', format='.2f'),
            alt.Tooltip('turpe_variable:Q', title='Part variable (€)', format='.2f'),
            alt.Tooltip('turpe_total:Q', title='Total (€)', format='.2f'),
        ]
    ).properties(
        width=800,
        height=500,
        title=f"Coût TURPE en fonction de la puissance souscrite - PDL {pdl_unique}"
    ).interactive()

    _graphique = mo.ui.altair_chart(chart)
    _graphique
    return


@app.cell(hide_code=True)
def _(resultats):
    # Export Excel
    excel_buffer = io.BytesIO()
    resultats.write_excel(excel_buffer)
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
