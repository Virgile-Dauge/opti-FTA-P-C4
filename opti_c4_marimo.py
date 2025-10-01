import marimo

__generated_with = "0.16.3"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import polars as pl
    from pathlib import Path
    from datetime import datetime
    import io
    return io, mo, pl


@app.cell(hide_code=True)
def _(mo):
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
def _(mo):
    mo.md("""## 📂 Upload de la courbe de charge""")
    return


@app.cell(hide_code=True)
def _(mo):
    file_upload = mo.ui.file(
        filetypes=[".csv"],
        kind="area",
        label="Sélectionnez votre fichier CSV au format Enedis"
    )
    file_upload
    return (file_upload,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## ⚙️ Paramètres TURPE""")
    return


@app.cell(hide_code=True)
def _(mo):
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
            label="CS_CU - Composante soutirage Courte Utilisation (€/kW/an)"
        ),
        "CS_LU": mo.ui.number(
            start=0,
            stop=100,
            step=0.01,
            value=30.16,
            label="CS_LU - Composante soutirage Longue Utilisation (€/kW/an)"
        ),
        "CMDPS": mo.ui.number(
            start=0,
            stop=50,
            step=0.01,
            value=12.41,
            label="CMDPS - Coût mensuel dépassement (€/h)"
        ),
        "CTA": mo.ui.number(
            start=1,
            stop=2,
            step=0.0001,
            value=1.2193,
            label="CTA - Contribution Tarifaire d'Acheminement"
        ),
    })
    params_turpe
    return (params_turpe,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 📊 Plage de puissances à tester""")
    return


@app.cell(hide_code=True)
def _(mo):
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
def _(file_upload, io, mo, pl):
    # Traitement du fichier CSV uploadé
    if file_upload.value is None:
        cdc = None
        msg_data = mo.md("⚠️ Veuillez uploader un fichier CSV pour commencer l'analyse")
    else:
        try:
            # Lire le contenu du fichier
            csv_content = file_upload.contents()

            # Parser avec Polars
            cdc_raw = pl.read_csv(io.BytesIO(csv_content), separator=';')

            # Vérification colonnes
            colonnes_requises = ['Horodate', 'Grandeur physique', 'Valeur', 'Pas']
            colonnes_manquantes = [col for col in colonnes_requises if col not in cdc_raw.columns]

            if colonnes_manquantes:
                cdc = None
                msg_data = mo.md(f"❌ Colonnes manquantes : {', '.join(colonnes_manquantes)}")
            else:
                # Filtrer PA et convertir
                cdc = (
                    cdc_raw
                    .filter(pl.col('Grandeur physique') == 'PA')
                    .with_columns([
                        pl.col('Horodate').str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S'),
                        (pl.col('Valeur') / 1000.0).alias('Valeur'),  # Watts -> kW
                        # Calculer le pas en heures dès le chargement
                        (
                            pl.col('Pas')
                            .str.strip_prefix('PT')
                            .str.strip_suffix('M')
                            .cast(pl.Int32)
                            / 60.0
                        ).alias('pas_heures')
                    ])
                    .select([
                        'Horodate',
                        'Valeur',
                        'Pas',
                        'pas_heures'
                    ])
                )

                if cdc.is_empty():
                    cdc = None
                    msg_data = mo.md("❌ Aucune donnée de Puissance Active (PA) trouvée")
                else:
                    duree_jours = (cdc['Horodate'].max() - cdc['Horodate'].min()).days
                    warning = f"⚠️ Seulement {duree_jours} jours de données (recommandé : 365 jours)" if duree_jours < 365 else ""

                    # Extraire le pas de temps
                    pas_exemple = cdc['Pas'][0]
                    pas_uniques = cdc['Pas'].n_unique()
                    warning_pas = f"\n⚠️ Attention : {pas_uniques} pas de temps différents détectés" if pas_uniques > 1 else ""

                    msg_data = mo.md(f"""
                    ✅ **Données chargées avec succès**

                    - Nombre de mesures : {len(cdc):,}
                    - Période : {cdc['Horodate'].min()} → {cdc['Horodate'].max()}
                    - Puissance max : {cdc['Valeur'].max():.2f} kW
                    - Pas de temps : {pas_exemple} {warning_pas}

                    {warning}
                    """)
        except Exception as e:
            cdc = None
            msg_data = mo.md(f"❌ Erreur lors de la lecture du fichier : {str(e)}")

    msg_data
    return (cdc,)


@app.cell
def _(cdc):
    cdc
    return


@app.cell
def _(pl):
    def expr_depassement(P: float) -> pl.Expr:
        """
        Expression Polars qui identifie les dépassements de puissance.

        Args:
            P: Puissance souscrite (kW)

        Returns:
            Expression Polars booléenne : True si dépassement, False sinon
        """
        return pl.col('Valeur') > P

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
    return (calculer_duree_depassement,)


@app.cell(hide_code=True)
def _(params_turpe):
    # Fonctions de calcul
    def fixe_CU(P):
        """Calcule le coût fixe annuel en option Courte Utilisation (CU)."""
        return (params_turpe.value["CG"] + params_turpe.value["CC"] + params_turpe.value["CS_CU"] * P) * params_turpe.value["CTA"]

    def fixe_LU(P):
        """Calcule le coût fixe annuel en option Longue Utilisation (LU)."""
        return (params_turpe.value["CG"] + params_turpe.value["CC"] + params_turpe.value["CS_LU"] * P) * params_turpe.value["CTA"]
    return fixe_CU, fixe_LU


@app.cell(hide_code=True)
def _(
    calculer_duree_depassement,
    cdc,
    fixe_CU,
    fixe_LU,
    mo,
    params_turpe,
    pl,
    plage_puissance,
):
    # Simulation TURPE
    if cdc is not None:
        # Génération de la plage de puissances
        P_min, P_max = plage_puissance.value
        Ps = list(range(P_min, P_max + 1))

        # Calcul pour chaque puissance
        resultats = []
        for P in Ps:
            cout_fixe_cu = fixe_CU(P)
            cout_fixe_lu = fixe_LU(P)
            duree_depassement_h = calculer_duree_depassement(cdc, P)
            cout_depassement = duree_depassement_h * params_turpe.value["CMDPS"]

            resultats.append({
                'PS': P,
                'CU fixe': cout_fixe_cu,
                'LU fixe': cout_fixe_lu,
                'Dépassement': cout_depassement,
                'Total CU': cout_fixe_cu + cout_depassement,
                'Total LU': cout_fixe_lu + cout_depassement
            })

        Simulation = pl.DataFrame(resultats)

        # Identifier les optimums
        idx_opt_CU = Simulation['Total CU'].arg_min()
        P_opt_CU = Simulation['PS'][idx_opt_CU]
        cout_opt_CU = Simulation['Total CU'][idx_opt_CU]

        idx_opt_LU = Simulation['Total LU'].arg_min()
        P_opt_LU = Simulation['PS'][idx_opt_LU]
        cout_opt_LU = Simulation['Total LU'][idx_opt_LU]

        msg_simulation = mo.md("✅ Simulation terminée")
    else:
        Simulation = None
        P_opt_CU = P_opt_LU = cout_opt_CU = cout_opt_LU = None
        msg_simulation = mo.md("⏸️ En attente des données")

    msg_simulation
    return P_opt_CU, P_opt_LU, Simulation, cout_opt_CU, cout_opt_LU


@app.cell(hide_code=True)
def _(P_opt_CU, P_opt_LU, Simulation, cout_opt_CU, cout_opt_LU, mo):
    # Affichage des résultats
    if Simulation is not None:
        economie = abs(cout_opt_CU - cout_opt_LU)
        recommandation = "CU" if cout_opt_CU < cout_opt_LU else "LU"
        P_recommande = P_opt_CU if cout_opt_CU < cout_opt_LU else P_opt_LU
        cout_recommande = min(cout_opt_CU, cout_opt_LU)

        resultats_md = mo.md(f"""
        ## 🎯 Résultats de l'optimisation

        ### 📌 Option COURTE UTILISATION (CU)
        - **Puissance optimale** : {P_opt_CU} kW
        - **Coût annuel** : {cout_opt_CU:.2f} €/an

        ### 📌 Option LONGUE UTILISATION (LU)
        - **Puissance optimale** : {P_opt_LU} kW
        - **Coût annuel** : {cout_opt_LU:.2f} €/an

        ---
        """)

    else:
        resultats_md = mo.md("")

    resultats_md
    return P_recommande, cout_recommande, economie, recommandation


@app.cell(hide_code=True)
def _(P_recommande, cout_recommande, economie, mo, recommandation):
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
def _(Simulation, mo):
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
def _(Simulation, io, mo):
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
