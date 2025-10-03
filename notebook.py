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

    # Imports standards
    import marimo as mo
    import polars as pl
    from pathlib import Path
    from datetime import datetime, time
    import io


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
    # 🔌 Optimisation TURPE - Calcul de Puissance Souscrite Optimale

    Cet outil permet de déterminer la **puissance souscrite optimale** pour un point de livraison
    électrique en fonction d'une courbe de charge réelle.

    Il simule les coûts d'acheminement (TURPE) pour différentes puissances et compare les options
    **CU** (Courte Utilisation) et **LU** (Longue Utilisation).
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
        label="Sélectionnez votre fichier CSV R63"
    )
    file_upload
    return (file_upload,)


@app.cell(hide_code=True)
def _():
    mo.md("""## ⚙️ Paramètres TURPE""")
    return


@app.cell(hide_code=True)
def _():
    params_turpe = mo.ui.dictionary({
        "CG": mo.ui.number(
            start=0,
            stop=1000,
            step=0.01,
            value=217.8,
            label="CG - Composante de gestion annuelle (€)"
        ),
        "CC": mo.ui.number(
            start=0,
            stop=1000,
            step=0.01,
            value=283.27,
            label="CC - Composante de comptage annuelle (€)"
        ),
        "CS_CU": mo.ui.number(
            start=0,
            stop=100,
            step=0.01,
            value=17.61,
            label="CS_CU - Coefficient pondérateur de la puissance Courte Utilisation (€/kVA/an)"
        ),
        "CS_LU": mo.ui.number(
            start=0,
            stop=100,
            step=0.01,
            value=30.16,
            label="CS_LU - Coefficient pondérateur de la puissance Longue Utilisation (€/kVA/an)"
        ),
        "CMDPS": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=12.41,
            label="CMDPS - Coût mensuel dépassement (€/h)"
        ),
        "CTA": mo.ui.number(
            start=0,
            stop=0.5,
            step=0.0001,
            value=0.2193,
            label="CTA - Contribution Tarifaire d'Acheminement"
        ),
        # Tarifs TURPE variable par cadran (c€/kWh)
        "HPH_CU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=6.91,
            label="HPH CU - Heures Pleines Hiver (c€/kWh)"
        ),
        "HCH_CU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=4.21,
            label="HCH CU - Heures Creuses Hiver (c€/kWh)"
        ),
        "HPB_CU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=2.13,
            label="HPB CU - Heures Pleines Basse saison (c€/kWh)"
        ),
        "HCB_CU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=1.52,
            label="HCB CU - Heures Creuses Basse saison (c€/kWh)"
        ),
        "HPH_LU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=5.69,
            label="HPH LU - Heures Pleines Hiver (c€/kWh)"
        ),
        "HCH_LU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=3.47,
            label="HCH LU - Heures Creuses Hiver (c€/kWh)"
        ),
        "HPB_LU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=2.01,
            label="HPB LU - Heures Pleines Basse saison (c€/kWh)"
        ),
        "HCB_LU": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=1.49,
            label="HCB LU - Heures Creuses Basse saison (c€/kWh)"
        ),
    })
    params_turpe
    return (params_turpe,)


@app.cell(hide_code=True)
def _():
    mo.md("""## 📊 Plage de puissances à tester""")
    return


@app.cell(hide_code=True)
def _():
    plage_puissance = mo.ui.range_slider(
        start=10,
        stop=100,
        step=1,
        value=[36, 66],
        label="Puissances à simuler (kW)",
        show_value=True
    )
    plage_puissance
    return (plage_puissance,)


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


@app.cell
def _(plages_hc):
    plages_hc
    return


@app.cell
def _():
    mo.md(r"""## Traitement de la courbe de charge""")
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


@app.cell(hide_code=True)
def fonctions_enrichissement():
    def expr_depassement(P: float) -> pl.Expr:
        """
        Expression Polars qui identifie les dépassements de puissance.

        Args:
            P: Puissance souscrite (kW)

        Returns:
            Expression Polars booléenne : True si dépassement, False sinon
        """
        return pl.col('Valeur') > P


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
    return enrichir_dataframe, expr_depassement


@app.cell(hide_code=True)
def _(expr_depassement, params_turpe):
    # Fonctions de calcul
    def fixe_CU(P):
        """Calcule le coût fixe annuel en option Courte Utilisation (CU)."""
        return (
            params_turpe.value["CG"]
            + params_turpe.value["CC"]
            + params_turpe.value["CS_CU"] * P
            ) * (1 + params_turpe.value["CTA"])

    def fixe_LU(P):
        """Calcule le coût fixe annuel en option Longue Utilisation (LU)."""
        return (
            params_turpe.value["CG"]
            + params_turpe.value["CC"]
            + params_turpe.value["CS_LU"] * P
            ) * (1 + params_turpe.value["CTA"])

    def calculer_duree_depassement(df: pl.DataFrame, P: float) -> float:
        """
        Calcule la durée totale de dépassement en heures.

        Méthode conforme Enedis :
        - Utilise la colonne 'pas_heures' déjà calculée dans le DataFrame
        - Chaque mesure en dépassement compte pour ce pas de temps
        - Durée totale (h) = Σ (dépassement × pas_heures)

        Args:
            df: DataFrame Polars avec colonnes 'Valeur', 'pas_heures'
            P: Puissance souscrite (kW)

        Returns:
            Durée totale de dépassement (heures)
        """
        return (
            df
            .with_columns([
                expr_depassement(P).alias('en_depassement')
            ])
            .select([
                (pl.col('en_depassement').cast(pl.Int32) * pl.col('pas_heures')).alias('duree_depassement')
            ])
            .sum()
            .item()
        )

    def calculer_turpe_variable(df: pl.DataFrame, params: dict, option: str) -> float:
        """
        Calcule le coût TURPE variable total pour une option tarifaire.

        Args:
            df: DataFrame enrichi avec colonnes 'cadran' et 'volume'
            params: Dictionnaire des paramètres TURPE
            option: 'CU' ou 'LU'

        Returns:
            Coût TURPE variable total annuel (€)
        """
        # Agréger les volumes par cadran
        volumes_cadrans = df.group_by('cadran').agg([
            pl.col('volume').sum().alias('volume_total')
        ])

        cout_total = 0.0
        for row in volumes_cadrans.iter_rows(named=True):
            cadran = row['cadran']
            volume = row['volume_total']
            # Tarif en c€/kWh, on convertit en €/kWh
            tarif_key = f"{cadran}_{option}"
            tarif = params.get(tarif_key, 0) / 100.0  # c€ → €
            cout_total += volume * tarif

        return cout_total
    return (
        calculer_duree_depassement,
        calculer_turpe_variable,
        fixe_CU,
        fixe_LU,
    )


@app.cell
def _():
    mo.md(r"""## Simulation en fonction de la puissance""")
    return


@app.cell(hide_code=True)
def simulation(
    calculer_duree_depassement,
    calculer_turpe_variable,
    cdc,
    fixe_CU,
    fixe_LU,
    params_turpe,
    plage_puissance,
):
    # Simulation TURPE
    mo.stop(cdc is None, output=mo.md("⏸️ En attente des données"))

    # Génération de la plage de puissances
    P_min, P_max = plage_puissance.value
    Ps = list(range(P_min, P_max + 1))

    # Calcul du TURPE variable (identique pour toutes les puissances)
    params = params_turpe.value
    cout_variable_cu = calculer_turpe_variable(cdc, params, 'CU')
    cout_variable_lu = calculer_turpe_variable(cdc, params, 'LU')

    # Calcul pour chaque puissance
    resultats = []
    for P in Ps:
        cout_fixe_cu = fixe_CU(P)
        cout_fixe_lu = fixe_LU(P)
        duree_depassement_h = calculer_duree_depassement(cdc, P)
        cout_depassement = duree_depassement_h * params["CMDPS"]

        resultats.append({
            'PS': P,
            'CU fixe': cout_fixe_cu,
            'LU fixe': cout_fixe_lu,
            'CU variable': cout_variable_cu,
            'LU variable': cout_variable_lu,
            'Dépassement': cout_depassement,
            'Total CU': cout_fixe_cu + cout_variable_cu + cout_depassement,
            'Total LU': cout_fixe_lu + cout_variable_lu + cout_depassement
        })

    Simulation = pl.DataFrame(resultats)

    # Identifier les optimums
    idx_opt_CU = Simulation['Total CU'].arg_min()
    P_opt_CU = Simulation['PS'][idx_opt_CU]
    cout_opt_CU = Simulation['Total CU'][idx_opt_CU]

    idx_opt_LU = Simulation['Total LU'].arg_min()
    P_opt_LU = Simulation['PS'][idx_opt_LU]
    cout_opt_LU = Simulation['Total LU'][idx_opt_LU]

    mo.md("✅ Simulation terminée")
    return P_opt_CU, P_opt_LU, Simulation, cout_opt_CU, cout_opt_LU


@app.cell(hide_code=True)
def _(P_opt_CU, P_opt_LU, Simulation, cout_opt_CU, cout_opt_LU):
    # Affichage des résultats
    mo.stop(Simulation is None, output=mo.md("⏸️ En attente de la simulation"))

    economie = abs(cout_opt_CU - cout_opt_LU)
    recommandation = "CU" if cout_opt_CU < cout_opt_LU else "LU"
    P_recommande = P_opt_CU if cout_opt_CU < cout_opt_LU else P_opt_LU
    cout_recommande = min(cout_opt_CU, cout_opt_LU)

    mo.md(f"""
    ## 🎯 Résultats de l'optimisation

    ### 📌 Option COURTE UTILISATION (CU)
    - **Puissance optimale** : {P_opt_CU} kW
    - **Coût annuel** : {cout_opt_CU:.2f} €/an

    ### 📌 Option LONGUE UTILISATION (LU)
    - **Puissance optimale** : {P_opt_LU} kW
    - **Coût annuel** : {cout_opt_LU:.2f} €/an

    ---
    """)
    return P_recommande, cout_recommande, economie, recommandation


@app.cell(hide_code=True)
def _(P_recommande, cout_recommande, economie, recommandation):
    mo.md(
        f"""
    ## 🎯 Résultats de l'optimisation
    ### ✅ RECOMMANDATION

    **Souscrire {P_recommande} kW en option {recommandation}**

    - Coût annuel : **{cout_recommande:.2f} €/an**
    - Économie vs autre option : **{economie:.2f} €/an**
    """
    )
    return


@app.cell(hide_code=True)
def _(Simulation):
    # Graphique interactif
    if Simulation is not None:
        import altair as alt

        # Préparer les données pour Altair
        df_plot = Simulation.select(['PS', 'Total CU', 'Total LU'])

        # Unpivot pour avoir une colonne "Option"
        df_melted = df_plot.unpivot(
            index='PS',
            on=['Total CU', 'Total LU'],
            variable_name='Option',
            value_name='Coût'
        )

        # Créer le graphique
        chart = alt.Chart(df_melted.to_pandas()).mark_line(point=True).encode(
            x=alt.X('PS:Q', title='Puissance souscrite (kW)'),
            y=alt.Y('Coût:Q', title='Coût annuel (€/an)'),
            color=alt.Color('Option:N', title='Option tarifaire'),
            tooltip=['PS', 'Option', alt.Tooltip('Coût:Q', format='.2f')]
        ).properties(
            width=700,
            height=400,
            title="Coût d'acheminement fixe annuel en fonction de la puissance souscrite"
        ).interactive()

        _graphique = mo.ui.altair_chart(chart)
    else:
        _graphique = mo.md("")

    _graphique
    return


@app.cell(hide_code=True)
def _(Simulation):
    # Export Excel
    if Simulation is not None:
        # Créer le fichier Excel en mémoire
        excel_buffer = io.BytesIO()
        Simulation.write_excel(excel_buffer)
        excel_data = excel_buffer.getvalue()

        _download_button = mo.download(
            data=excel_data,
            filename="Simulation_TURPE.xlsx",
            label="📥 Télécharger les résultats (Excel)",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        _download_button = mo.md("")

    _download_button
    return


if __name__ == "__main__":
    app.run()
