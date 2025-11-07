import marimo

__generated_with = "0.16.5"
app = marimo.App(width="medium")

async with app.setup(hide_code=True):
    # Installation des dépendances pour WASM (Pyodide)
    import sys
    if "pyodide" in sys.modules:
        import micropip
        await micropip.install("polars")

    # Imports standards
    import marimo as mo
    import polars as pl
    from pathlib import Path
    import subprocess


@app.cell(hide_code=True)
def _():
    mo.md(
        r"""
    # 📦 Extraction et traitement des fichiers ZIP

    Cet outil permet de :
    - Sélectionner un dossier contenant des fichiers ZIP protégés
    - Choisir le type de fichier à extraire (M-2 ou M-6)
    - Extraire automatiquement tous les ZIP avec **7z** (via `extract_all.sh`)
    - Déverrouiller les ZIP avec le mot de passe depuis `mdp.txt`
    - Ignorer les fichiers déjà extraits
    - Lire et concaténer tous les fichiers CSV extraits avec Polars
    """
    )
    return


@app.cell(hide_code=True)
def _():
    mo.md("""## ⚙️ Configuration""")
    return


@app.cell(hide_code=True)
def _():
    type_fichier = mo.ui.multiselect(
        options=["M-2", "M-6"],
        value=["M-2", "M-6"],
        label="Types de fichiers à traiter"
    )
    type_fichier
    return (type_fichier,)


@app.cell(hide_code=True)
def _():
    mo.md("""### 📂 Sélection du dossier""")
    return


@app.cell(hide_code=True)
def _():
    folder_browser = mo.ui.file_browser(
        initial_path=".",
        selection_mode="directory",
        multiple=False,
        label="Sélectionnez le dossier contenant les fichiers ZIP"
    )
    folder_browser
    return (folder_browser,)


@app.cell(hide_code=True)
def _(folder_browser):
    mo.stop(not folder_browser.value, mo.md("⚠️ Veuillez sélectionner un dossier"))

    folder_path = folder_browser.path(0)

    mo.stop(folder_path is None, mo.md("⚠️ Aucun dossier sélectionné"))
    mo.stop(not folder_path.exists(), mo.md(f"❌ Le dossier `{folder_path}` n'existe pas"))
    mo.stop(not folder_path.is_dir(), mo.md(f"❌ `{folder_path}` n'est pas un dossier"))

    mo.md(f"✅ Dossier sélectionné : `{folder_path}`")
    return (folder_path,)


@app.cell
def _():
    mo.md(r"""## 🔑 Lecture du mot de passe""")
    return


@app.cell(hide_code=True)
def _(folder_path):
    mdp_file = folder_path / "mdp.txt"

    mo.stop(not mdp_file.exists(), mo.md(f"❌ Fichier `mdp.txt` non trouvé dans `{folder_path}`"))

    password = mdp_file.read_text().strip()

    mo.md(f"✅ Mot de passe chargé depuis `mdp.txt`")
    return (password,)


@app.cell
def _():
    mo.md(r"""## 🔓 Extraction et lecture des CSV M-2""")
    return


@app.function(hide_code=True)
def extract_all_with_7z(folder_path: Path, password: str) -> tuple[str, str]:
    """
    Extrait tous les ZIP d'un dossier en utilisant le script bash extract_all.sh avec 7z.

    Args:
        folder_path: Chemin vers le dossier contenant les ZIP
        password: Mot de passe pour déverrouiller les ZIP

    Returns:
        Tuple (stdout, stderr)
    """
    # Cherche le script extract_all.sh
    script_path = Path(__file__).parent / "extract_all.sh"

    if not script_path.exists():
        raise FileNotFoundError(f"Script extract_all.sh introuvable : {script_path}")

    # Exécute le script dans le dossier cible
    result = subprocess.run(
        ['bash', str(script_path), password],
        cwd=str(folder_path),
        capture_output=True,
        text=True,
        timeout=300  # 5 minutes max
    )

    return result.stdout, result.stderr


@app.cell(hide_code=True)
def _(folder_path, password, type_fichier):
    mo.stop("M-2" not in type_fichier.value, "")

    # Extraction avec 7z via le script bash
    try:
        stdout, stderr = extract_all_with_7z(folder_path, password)

        # Affichage du résultat de l'extraction
        _extraction_log = stdout.replace('\n', '\n\n')

        mo.md(f"""
    ## 📊 Résultat de l'extraction (7z)

    {_extraction_log}

    ---
        """)
    except subprocess.TimeoutExpired:
        mo.md("❌ **Timeout** : L'extraction a pris trop de temps (>5 minutes)")
    except FileNotFoundError as e:
        mo.md(f"❌ **Erreur** : {str(e)}")
    except Exception as e:
        mo.md(f"❌ **Erreur inattendue** : {str(e)}")

    # Lecture des CSV M-2 extraits
    csv_files = sorted([f for f in folder_path.glob("ENEDIS_*.csv") if "M-2" in f.name])

    all_dataframes = []
    for csv_file in csv_files:
        try:
            df = pl.read_csv(csv_file, separator=';')
            all_dataframes.append(df)
        except Exception as e:
            mo.md(f"⚠️ Impossible de lire `{csv_file.name}` : {str(e)}")

    mo.md(f"✅ **{len(all_dataframes)} fichiers CSV M-2 chargés**")
    return (all_dataframes,)


@app.cell(hide_code=True)
def _(all_dataframes, type_fichier):
    mo.stop("M-2" not in type_fichier.value, "")
    mo.stop(len(all_dataframes) == 0, mo.md("❌ Aucun DataFrame M-2 chargé"))

    # Concaténation de tous les DataFrames
    df_concat = (
        pl.concat(all_dataframes)
        .with_columns([
            pl.col('DATE_BASCULE').str.to_date()
        ])
    )

    _nb_lignes = len(df_concat)
    _nb_colonnes = len(df_concat.columns)
    _nb_fichiers = len(all_dataframes)

    mo.md(f"""
    ## ✅ Concaténation terminée

    - **{_nb_fichiers}** fichiers CSV chargés
    - **{_nb_lignes:,}** lignes au total
    - **{_nb_colonnes}** colonnes
    """)
    return (df_concat,)


@app.cell
def _(df_concat):
    df_concat
    return


@app.cell
def _():
    mo.md(r"""## 📋 Lecture de la base client""")
    return


@app.cell(hide_code=True)
def _(folder_path):
    # Lecture du fichier base_client.xlsx
    base_client_file = folder_path / "base_client.xlsx"

    mo.stop(not base_client_file.exists(), mo.md(f"❌ Fichier `base_client.xlsx` non trouvé dans `{folder_path}`"))

    base_client = pl.read_excel(base_client_file)

    _nb_clients = len(base_client)
    _colonnes = ", ".join([f"`{col}`" for col in base_client.columns])

    mo.md(f"""
    ✅ **Base client chargée** : {_nb_clients} clients

    Colonnes : {_colonnes}
    """)
    return (base_client,)


@app.cell
def _():
    mo.md(r"""## 🔗 Jointure avec les données de consommation""")
    return


@app.cell(hide_code=True)
def _(base_client, df_concat):
    # Left join : garder uniquement les lignes de df_concat correspondant aux clients actuels
    # Harmonisation du type de la colonne PRM (conversion en string)
    df_concat_typed = df_concat.with_columns([
        pl.col("PRM").cast(pl.Utf8)
    ])

    df_final = base_client.join(df_concat_typed, on="PRM", how="left")

    _nb_avant = len(df_concat)
    _nb_apres = len(df_final)
    _nb_clients = len(base_client)

    mo.md(f"""
    ✅ **Jointure terminée**

    - **{_nb_clients}** clients dans la base client
    - **{_nb_avant:,}** lignes de consommation avant jointure
    - **{_nb_apres:,}** lignes après jointure (filtrées sur clients actuels)
    """)
    return (df_final,)


@app.cell
def _():
    mo.md(r"""## 👀 Aperçu des données finales""")
    return


@app.cell(hide_code=True)
def _(df_final):
    df_final
    return


@app.cell
def _():
    mo.md(r"""## 📤 Export M-2 par mois""")
    return


@app.cell(hide_code=True)
def _(df_final, type_fichier):
    mo.stop("M-2" not in type_fichier.value, "")

    # Ajout d'une colonne mois pour le groupement (en filtrant les null)
    df_with_month = (
        df_final
        .filter(pl.col("DATE_BASCULE").is_not_null())
        .with_columns([
            pl.col("DATE_BASCULE").dt.strftime("%Y-%m").alias("mois")
        ])
    )

    # Liste des mois uniques avec statistiques
    mois_stats = (
        df_with_month
        .group_by("mois")
        .agg([
            pl.len().alias("nb_lignes")
        ])
        .sort("mois")
    )

    _nb_mois = len(mois_stats)
    _stats_text = "\n".join([
        f"- **{row['mois']}** : {row['nb_lignes']:,} lignes"
        for row in mois_stats.iter_rows(named=True)
    ])

    mo.md(f"""
    ### 📊 Statistiques par mois

    {_nb_mois} mois détectés :

    {_stats_text}
    """)
    return df_with_month, mois_stats


@app.cell(hide_code=True)
def _(df_with_month, folder_path, mois_stats, type_fichier):
    mo.stop("M-2" not in type_fichier.value, "")

    # Export d'un CSV M-2 par mois
    export_logs = []

    for row in mois_stats.iter_rows(named=True):
        mois = row['mois']
        nb_lignes = row['nb_lignes']

        # Filtrer les données du mois
        df_mois = df_with_month.filter(pl.col("mois") == mois)

        # Nom du fichier M-2
        export_file = folder_path / f"export_M2_{mois}.csv"

        # Export CSV
        df_mois.write_csv(export_file, separator=";")

        export_logs.append(f"✅ `{export_file.name}` : {nb_lignes:,} lignes")

    _export_summary = "\n".join(export_logs)

    mo.md(f"""
    ### ✅ Exports terminés

    {len(export_logs)} fichiers créés dans `{folder_path}` :

    {_export_summary}
    """)
    return


@app.cell
def _():
    mo.md(r"""## 🔓 Extraction et lecture des CSV M-6""")
    return


@app.cell(hide_code=True)
def _(folder_path, password, type_fichier):
    mo.stop("M-6" not in type_fichier.value, "")

    # Extraction avec 7z via le script bash (identique à M-2)
    try:
        stdout_m6, stderr_m6 = extract_all_with_7z(folder_path, password)

        # Affichage du résultat de l'extraction
        _extraction_log_m6 = stdout_m6.replace('\n', '\n\n')

        mo.md(f"""
    ## 📊 Résultat de l'extraction M-6 (7z)

    {_extraction_log_m6}

    ---
        """)
    except subprocess.TimeoutExpired:
        mo.md("❌ **Timeout M-6** : L'extraction a pris trop de temps (>5 minutes)")
    except FileNotFoundError as e:
        mo.md(f"❌ **Erreur M-6** : {str(e)}")
    except Exception as e:
        mo.md(f"❌ **Erreur inattendue M-6** : {str(e)}")
    return


@app.cell(hide_code=True)
def _(folder_path, type_fichier):
    mo.stop("M-6" not in type_fichier.value, "")

    import re

    # Trouver tous les CSV M-6
    csv_files_m6 = sorted([f for f in folder_path.glob("ENEDIS_*.csv") if "M-6" in f.name])

    all_dataframes_m6 = []
    for csv_file_m6 in csv_files_m6:
        try:
            df_m6 = pl.read_csv(csv_file_m6, separator=';')

            # Extraire le timestamp du nom de fichier (derniers 14 chiffres avant .csv)
            # Ex: 2026-04-ENEDIS_TURPE7HC_M-6_GRD-F091_001_001_20250918100525.csv
            #                                                     ^^^^^^^^^^^^^^
            match = re.search(r'(\d{14})\.csv$', csv_file_m6.name)
            timestamp = match.group(1) if match else "00000000000000"

            # Ajouter métadonnées pour traçabilité
            df_m6 = df_m6.with_columns([
                pl.lit(timestamp).alias("_source_timestamp"),
                pl.lit(csv_file_m6.name).alias("_source_file")
            ])
            all_dataframes_m6.append(df_m6)
        except Exception as e:
            mo.md(f"⚠️ Impossible de lire `{csv_file_m6.name}` : {str(e)}")

    # Concaténation (avec how="diagonal" pour gérer les colonnes différentes)
    if len(all_dataframes_m6) > 0:
        df_m6_concat = pl.concat(all_dataframes_m6, how="diagonal")
        mo.md(f"✅ **{len(all_dataframes_m6)} fichiers CSV M-6 chargés** : {len(df_m6_concat):,} lignes")
    else:
        mo.md("⚠️ Aucun fichier M-6 trouvé")
        df_m6_concat = None
    return (df_m6_concat,)


@app.cell
def _():
    mo.md(r"""## 🔗 Jointure M-6 avec base client""")
    return


@app.cell(hide_code=True)
def _(base_client, df_m6_concat, type_fichier):
    mo.stop("M-6" not in type_fichier.value, "")
    mo.stop(df_m6_concat is None, mo.md("⚠️ Aucune donnée M-6 à traiter"))

    # Conversion DATE_BASCULE + cast PRM
    df_m6_typed = df_m6_concat.with_columns([
        pl.col("DATE_BASCULE").str.to_date(),
        pl.col("PRM").cast(pl.Utf8)
    ])

    # Join avec base_client
    df_m6_joined = base_client.join(df_m6_typed, on="PRM", how="left")

    mo.md(f"✅ **Jointure M-6 terminée** : {len(df_m6_joined):,} lignes")
    return (df_m6_joined,)


@app.cell
def _():
    mo.md(r"""## 🔍 Dédoublonnage M-6""")
    return


@app.cell(hide_code=True)
def _(df_m6_joined, type_fichier):
    mo.stop("M-6" not in type_fichier.value, "")
    mo.stop(df_m6_joined is None, "")

    nb_avant_m6 = len(df_m6_joined)

    # Dédoublonnage : garder la ligne du fichier le plus récent par PRM
    df_m6_dedup = (
        df_m6_joined
        .sort("_source_timestamp", descending=True)  # Plus récent en premier
        .unique(subset=["PRM"], keep="first")
        .drop(["_source_timestamp", "_source_file"])  # Retirer les colonnes techniques
    )

    nb_apres_m6 = len(df_m6_dedup)
    nb_duplicatas_m6 = nb_avant_m6 - nb_apres_m6

    mo.md(f"""
    ✅ **Dédoublonnage M-6 terminé**

    - **{nb_avant_m6:,}** lignes avant dédoublonnage
    - **{nb_apres_m6:,}** lignes après dédoublonnage
    - **{nb_duplicatas_m6:,}** duplicatas supprimés ({nb_duplicatas_m6/nb_avant_m6*100:.1f}%)
    """)
    return (df_m6_dedup,)


@app.cell
def _():
    mo.md(r"""## 📤 Export M-6 consolidé""")
    return


@app.cell(hide_code=True)
def _(df_m6_dedup, folder_path, type_fichier):
    mo.stop("M-6" not in type_fichier.value, "")
    mo.stop(df_m6_dedup is None, "")

    # Export unique
    export_file_m6 = folder_path / "fichier_complet_M-6.csv"
    df_m6_dedup.write_csv(export_file_m6, separator=";")

    mo.md(f"""
    ✅ **Export M-6 terminé**

    Fichier créé : `{export_file_m6.name}` ({len(df_m6_dedup):,} lignes)
    """)
    return


if __name__ == "__main__":
    app.run()
