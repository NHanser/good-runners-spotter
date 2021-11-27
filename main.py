from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import os

def export_inscrits_to_csv(site="SPORT-UP", course_id=36711, max_inscrits=1240, sex_filter=None, output_dir="output"):
    print("Export de la liste des inscrits...")
    inscrits = []
    # TODO : develop connectors for other site
    if site == "SPORT-UP":
        for i in range(0,max_inscrits,75):
            URL = f"https://www.sport-up.fr/www/inscription_en_ligne_2.0/module/listing_2-{course_id}-{i}-75.htm"
            page = requests.get(URL)
            soup = BeautifulSoup(page.content, "html.parser")
            table = soup.find(id="listeinscrit")
            indexes = {"nom": 2, "prenom": 3, "sexe": 4}
            for row in table.findAll("tr"):
                cells = row.findAll("td")
                if len(cells) > 0:
                    nom = cells[2].text
                    prenom = cells[3].text
                    sexe = cells[4].text
                    if sex_filter is None or sexe == sex_filter:
                        inscrits.append({"nom": nom, "prenom": prenom})
                else:
                    cells = row.findAll("th")
                    if len(cells) > 0:
                        for icell in range(len(cells)):
                            if cells[icell].text == "Nom":
                                indexes["nom"] = icell
                            if cells[icell].text == "Prénom":
                                indexes["prenom"] = icell
                            if cells[icell].text == "Sexe":
                                indexes["sexe"] = icell

    df = pd.DataFrame(data=inscrits)
    df.to_csv(f"{output_dir}/{course_id}-liste_inscrits.csv")


def f_remove_accents(old):
    """
    Removes common accent characters, lower form.
    Uses: regex.
    """
    new = old.lower()
    new = re.sub(r'[àáâãäå]', 'a', new)
    new = re.sub(r'[èéêë]', 'e', new)
    new = re.sub(r'[ìíîï]', 'i', new)
    new = re.sub(r'[òóôõö]', 'o', new)
    new = re.sub(r'[ùúûü]', 'u', new)
    new = re.sub(r'[ç]', 'c', new)
    new = re.sub(r'[\']', '%3F', new)
    return new


def check_kikourou_to_csv(course_id,output_dir="output"):
    print("Check perfs sur Kikourou...")
    df = pd.read_csv(f"{output_dir}/{course_id}-liste_inscrits.csv")
    resultats = []
    for index, row in df.iterrows():
        nom=f_remove_accents(row["nom"]).replace(' ','+')
        prenom=f_remove_accents(row["prenom"]).replace(' ','+')
        URL = f"http://www.kikourou.net/resultats/{nom}+{prenom}.html"
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        table = soup.find(id="tableresultats")
        for t_row in table.findAll("tr"):
            cells = t_row.findAll("td")
            if len(cells) > 0:
                course = cells[1].text.replace(" \r\n      (les résultats, c'est moi ?)","").lower()
                resultats.append({"nom": row["nom"], "prenom": row["prenom"], "date":cells[0].text, "course": course, "perf": cells[2].text})

    df = pd.DataFrame(data=resultats)
    df.to_csv(f"{output_dir}/{course_id}-resultats_kikourou.csv", index=False)


def convert_time_seconds(text):
    try:
        if text[-1] == "'":
            text = text[:-1]+'"'
    except TypeError:
        print(f"Error with text {text}")
        return -1
    text = text.replace("'\"", "\"")
    RE_IDENTIFIER = re.compile("^(([0-3]?\d|2[0-3])h)?([0-5]?\d)?('?([0-5]?\d))?\"$")
    if match := RE_IDENTIFIER.search(text):
        dum, hour, minutes, dum, seconds = match.groups()
        try:
            if hour is None:
                hour = 0
            seconds = (int(hour)*3600)+int(minutes)*60+int(seconds)
        except TypeError as e:
            print(f"Error with hour = {hour}, minutes = {minutes}, seconds = {seconds} for text = {text}")
        return seconds
    else:
        print(f'Invalid identifier {text}')
        return -1


def filter_perfs_to_csv(course_id, min_perf_10km=None, max_perf_10km=None, min_perf_semi=None, max_perf_semi=None,output_dir="output"):
    print("Filtre des perfs...")
    df = pd.read_csv(f"{output_dir}/{course_id}-resultats_kikourou.csv")
    df["perf_seconds"] = df["perf"].apply(convert_time_seconds)
    cond1 = ((df["course"].str.contains("10km"))&(df["perf_seconds"] < max_perf_10km)&(df["perf_seconds"] > min_perf_10km))
    cond2 = ((df["course"].str.contains("10 km"))&(df["perf_seconds"] < max_perf_10km)&(df["perf_seconds"] > min_perf_10km))
    cond3 = ((df["course"].str.contains("semi"))&(~df["course"].str.contains("10km"))&(~df["course"].str.contains("10 km"))&(df["perf_seconds"] < max_perf_semi)&(df["perf_seconds"] > min_perf_semi))
    cond4 = ((df["course"].str.contains("Semi"))&(~df["course"].str.contains("10km"))&(~df["course"].str.contains("10 km"))&(df["perf_seconds"] < max_perf_semi)&(df["perf_seconds"] > min_perf_semi))
    df_filtered = df[cond1|cond2|cond3|cond4]
    df_filtered.to_csv(f"{output_dir}/{course_id}-bons_coureurs_all_results.csv", index=False)


def best_perfs_to_html(course_id, output_dir="output"):
    print("Filtre sur les meilleurs perfs individuelles...")
    df = pd.read_csv(f"{output_dir}/{course_id}-bons_coureurs_all_results.csv")
    df.drop("perf_seconds",axis=1).to_html(f"{output_dir}/{course_id}-Bons_coureurs_all_results.html")
    df_unique_names = df[["nom","prenom"]].drop_duplicates()
    all_perfs = []
    for index, row in df_unique_names.iterrows():
        nom = row["nom"]
        prenom = row["prenom"]
        df_coureur = df[(df["nom"] == nom) & (df["prenom"] == prenom)]
        df_coureur_10km = df_coureur[df_coureur["course"].str.contains("10 km")|df_coureur["course"].str.contains("10km")]
        df_coureur_semi = df_coureur[(df_coureur["course"].str.contains("semi")|df_coureur["course"].str.contains("Semi"))&~df_coureur["course"].str.contains("10 km")&~df_coureur["course"].str.contains("10km")]
        perfs = []
        if len(df_coureur_10km) > 0:
            perfs.append(df_coureur_10km["perf_seconds"].min())
        if len(df_coureur_semi) > 0:
            perfs.append(df_coureur_semi["perf_seconds"].min())
        df_best_perfs_coureur = df_coureur[df_coureur["perf_seconds"].isin(perfs)]
        all_perfs.append(df_best_perfs_coureur)
    df_final = pd.concat(all_perfs,axis=0)
    df_final.to_html(f"{output_dir}/Best_perfs_inscrits.html")


def check_Nice_Cannes_20km():
    min_perf_10_km_s = 1560
    max_perf_10_km_s = 2160
    min_perf_semi_s = 3500
    max_perf_semi_s = 4620
    output_dir = "./output"
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    course_id = 36711
    export_inscrits_to_csv(site="SPORT-UP", course_id=course_id, max_inscrits=1240, sex_filter="Masculin", output_dir=output_dir)
    check_kikourou_to_csv(course_id=course_id, output_dir=output_dir)
    filter_perfs_to_csv(course_id=course_id,
                        min_perf_10km=min_perf_10_km_s, max_perf_10km=max_perf_10_km_s,
                        min_perf_semi=min_perf_semi_s, max_perf_semi=max_perf_semi_s,
                        output_dir=output_dir)
    best_perfs_to_html(course_id=course_id, output_dir=output_dir)


check_Nice_Cannes_20km()