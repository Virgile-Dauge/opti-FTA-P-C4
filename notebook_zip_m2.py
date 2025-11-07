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
    type_fichier = mo.ui.radio(
        options=["M-2", "M-6"],
        value="M-2",
        label="Type de fichier à extraire"
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
    mo.md(r"""## 🔓 Extraction et lecture des CSV""")
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

    # Lecture des CSV extraits
    pattern = type_fichier.value
    csv_files = sorted([f for f in folder_path.glob("ENEDIS_*.csv") if pattern in f.name])

    all_dataframes = []
    for csv_file in csv_files:
        try:
            df = pl.read_csv(csv_file, separator=';')
            all_dataframes.append(df)
        except Exception as e:
            mo.md(f"⚠️ Impossible de lire `{csv_file.name}` : {str(e)}")

    mo.md(f"✅ **{len(all_dataframes)} fichiers CSV de type '{pattern}' chargés**")
    return (all_dataframes,)


@app.cell(hide_code=True)
def _(all_dataframes):
    mo.stop(len(all_dataframes) == 0, mo.md("❌ Aucun DataFrame chargé"))

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
    mo.md(r"""## 📤 Export par mois""")
    return


@app.cell(hide_code=True)
def _(df_final):
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
    return (df_with_month, mois_stats)


@app.cell(hide_code=True)
def _(df_with_month, folder_path, mois_stats):
    # Export d'un CSV par mois
    export_logs = []

    for row in mois_stats.iter_rows(named=True):
        mois = row['mois']
        nb_lignes = row['nb_lignes']

        # Filtrer les données du mois
        df_mois = df_with_month.filter(pl.col("mois") == mois)

        # Nom du fichier
        export_file = folder_path / f"export_{mois}.csv"

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


if __name__ == "__main__":
    app.run()
