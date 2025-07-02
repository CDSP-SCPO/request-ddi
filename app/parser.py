# -- STDLIB
from datetime import datetime

# -- THIRDPARTY
from bs4 import BeautifulSoup


class XMLParser:
    def __init__(self):
        self.errors = []

    def parse_file(self, file, seen_invalid_dois):
        """Parse un fichier XML et retourne les données extraites ou None s’il y a une erreur."""
        try:
            file.seek(0)
            content = file.read().decode('utf-8')
            soup = BeautifulSoup(content, "xml")

            doi_tag = soup.find("IDNo", attrs={"agency": "DataCite"}) or soup.find("IDNo")
            doi = doi_tag.text.strip() if doi_tag else None

            if not doi or not doi.startswith("doi:"):
                if doi not in seen_invalid_dois:
                    seen_invalid_dois.add(doi)
                    self.errors.append(
                        f"<strong>{file.name}</strong> : DOI invalide '<strong>{doi}</strong>' (doit commencer par 'doi:')."
                    )
                return None

            data = []
            for line in soup.find_all("var"):
                categories = " | ".join([
                    ','.join([
                        cat.find("catValu").text.strip() if cat.find("catValu") else '',
                        cat.find("labl").text.strip() if cat.find("labl") else ''
                    ])
                    for cat in line.find_all("catgry")
                ])

                data.append([
                    doi,
                    line["name"].strip(),
                    line.find("labl").text.strip() if line.find("labl") else "",
                    line.find("qstnLit").text.strip() if line.find("qstnLit") else "",
                    categories,
                    line.find("universe").text.strip() if line.find("universe") else "",
                    line.find("notes").text.strip() if line.find("notes") else "",
                ])

            return data

        except Exception as e:
            self.errors.append(f"Erreur lors du parsing du fichier {file.name}: {str(e)}")
            return None
