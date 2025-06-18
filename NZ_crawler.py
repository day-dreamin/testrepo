import requests
import re
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

# --- Configuration ---
BASE_URL = "https://www.courtsofnz.govt.nz/"
SEARCH_URL = "https://www.courtsofnz.govt.nz/the-courts/supreme-court/judgments-supreme"
YEARS_TO_CRAWL = range(2004, 2026) # 2004 to 2025 inclusive

# REGEX patterns to find paragraphs containing key phrases
PATTERNS = {
    "The question is whether": r"(?i)(?:[^\n.!?]*[\s\n]){0,50}The question is whether.*?(?:[\.!?](?=\s|$))",
    "The leading case": r"(?i)[^\n]*The leading case[^\n]*",
    "The leading authority": r"(?i)[^\n]*The leading authority[^\n]*",
    "The issue here is whether": r"(?i)[^\n]*The issue here is whether[^\n]*",
    "The applicable test is": r"(i)[^\n]*The applicable test is[^\n]*",
    "The applicable threshold is": r"(?i)[^\n]*The applicable threshold is[^\n]*"
}

# --- Main Script ---

def get_soup(url, params=None):
    """Fetches a URL and returns a BeautifulSoup object."""
    # *** FIX: Add a User-Agent header to mimic a real browser ***
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        # Pass the headers with the request
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status() # Raise an error for bad status codes (like 403)
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_text_from_pdf(pdf_url):
    """Downloads a PDF and extracts its full text."""
    # *** FIX: Also send headers when downloading the PDF ***
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(pdf_url, headers=headers, timeout=30)
        response.raise_for_status()
        # Use a context manager for writing the file to ensure it's closed properly
        with open("temp_judgment.pdf", "wb") as f:
            f.write(response.content)
        
        full_text = ""
        with pdfplumber.open("temp_judgment.pdf") as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        return full_text
    except Exception as e:
        print(f"Error processing PDF {pdf_url}: {e}")
        return ""

def main():
    """Main function to run the crawler."""
    print("Starting crawler...")
    all_propositions = []

    for year in YEARS_TO_CRAWL:
        print(f"\n--- Processing Year: {year} ---")
        start_index = 0
        while True:
            print(f"Fetching page with start index: {start_index}...")
            params = {'Search': '', 'CaseNum': '', 'Year': year, 'action_search': 'Search', 'start': start_index}
            soup = get_soup(SEARCH_URL, params=params)

            if not soup:
                # Error message is already printed inside get_soup, so just break
                break

            results = soup.find_all('div', class_='result')
            
            if not results:
                print(f"No more results found for {year}. Moving to next year.")
                break
            
            for result in results:
                case_title_tag = result.find('h3').find('a')
                meta_data_tag = result.find('p', class_='meta-data')

                if not case_title_tag or not meta_data_tag:
                    continue

                case_title = case_title_tag.get_text(strip=True)
                case_details_url = urljoin(BASE_URL, case_title_tag['href'])
                
                citation_match = re.search(r'\[\d{4}\] NZSC \d+', meta_data_tag.get_text())
                citation = citation_match.group(0) if citation_match else f"UNKNOWN_CITATION_{year}"
                
                print(f"  Found Case: {case_title} ({citation})")

                details_soup = get_soup(case_details_url)
                if not details_soup:
                    continue
                
                pdf_tag = details_soup.find('a', href=re.compile(r'\.pdf$'))
                if not pdf_tag:
                    print(f"    - PDF link not found for {case_title}")
                    continue

                pdf_url = urljoin(BASE_URL, pdf_tag['href'])
                
                print(f"    - Extracting text from PDF: {pdf_url}")
                document_text = extract_text_from_pdf(pdf_url)

                if not document_text:
                    print(f"    - Failed to extract text from PDF.")
                    continue

                for pattern_name, regex in PATTERNS.items():
                    matches = re.finditer(regex, document_text)
                    for match in matches:
                        proposition_data = {
                            'doc_id': citation.replace('[', '').replace(']', '').replace(' ', '_'),
                            'title': case_title,
                            'url': pdf_url,
                            'proposition': match.group(0).strip(),
                            'citation': citation,
                            'pattern_matched': pattern_name
                        }
                        all_propositions.append(proposition_data)
                        print(f"      > Match found for: '{pattern_name}'")

                time.sleep(1) 
            
            start_index += 10
    
    print("\n--- Crawling complete. Saving data... ---")
    
    if not all_propositions:
        print("No propositions were extracted. The output files will be empty.")
        return

    df = pd.DataFrame(all_propositions)
    # Ensure UTF-8 encoding is used for CSV for better compatibility
    df.to_csv("NZSC_Propositions_Export.csv", index=False, encoding='utf-8-sig')
    df.to_excel("NZSC_Propositions_Export.xlsx", index=False)
    
    print(f"\nSuccessfully saved {len(all_propositions)} propositions to:")
    print("- NZSC_Propositions_Export.csv")
    print("- NZSC_Propositions_Export.xlsx")

if __name__ == '__main__':
    main()
