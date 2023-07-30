import os
import json
import requests
from concurrent.futures import ThreadPoolExecutor


def download_url(url, folder, filename):
    if(not url):
        return
    
    print('Downloading: ', url, " -to- ",  folder, filename)
    response = requests.get(url)
    if response.ok:
        save_path = os.path.join(folder, filename)
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded {url} to {save_path}\n\n")
    else:
        print(f"Failed to download {url}")

def get_url(code, base_url):
    if not code: 
        return ""
    return f"{base_url}{code}dd.zip"

def download_urls_concurrently(json_file, concurrency, out_dir, base_url):
    with open(json_file, 'r') as f:
        data = json.load(f)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for classNum, subjects in data.items():
            for subject, books in subjects.items():
              # print(classNum, subject, books)
              folder = os.path.join(os.getcwd(), out_dir, classNum, subject.strip())
              os.makedirs(folder, exist_ok=True)
              futures = [executor.submit(download_url, get_url(book.get("code"), base_url), folder, book.get("text") + ".zip")
                        for book in books]
        for future in futures:
            future.result()


if __name__ == "__main__":
    base_url = "https://ncert.nic.in/textbook/pdf/"
    json_file_path = "data.json"  # Replace with the path to your JSON file
    out_dir = "downloads"
    concurrent_downloads = 10  # Set the number of concurrent downloads here

    download_urls_concurrently(json_file_path, concurrent_downloads, out_dir, base_url)
