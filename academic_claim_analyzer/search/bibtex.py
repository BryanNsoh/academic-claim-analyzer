# academic_claim_analyzer/search/bibtex.py

import requests
from typing import Optional

def get_bibtex_from_doi(doi: str) -> Optional[str]:
    """
    Fetch BibTeX data for a given DOI using the Crossref API.
    """
    url = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    return None

def get_bibtex_from_title(title: str, authors: list, year: int) -> Optional[str]:
    """
    Search for a paper using its title, authors, and year, then fetch its BibTeX data using the Crossref API.
    """
    query = f"{title} {' '.join(authors)} {year}"
    url = f"https://api.crossref.org/works?query={query}&rows=1"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['message']['items']:
            doi = data['message']['items'][0].get('DOI')
            if doi:
                return get_bibtex_from_doi(doi)
    return None

# Test with main code
def main():
    # Example 1: Get BibTeX from DOI
    doi = "10.1016/j.ifacol.2020.12.237"
    bibtex_from_doi = get_bibtex_from_doi(doi)
    print("BibTeX from DOI:")
    print(bibtex_from_doi)
    print("\n")

    # Example 2: Get BibTeX from title, authors, and year
    title = "Optimal control of greenhouse climate using PID and MPC algorithms"
    authors = ["Hasni", "A.", "Taibi", "R.", "Draoui", "B.", "Boulard", "T."]
    year = 2020
    bibtex_from_title = get_bibtex_from_title(title, authors, year)
    print("BibTeX from title, authors, and year:")
    print(bibtex_from_title)

if __name__ == "__main__":
    main()