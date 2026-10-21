import concurrent.futures
import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


URL = "https://www.ssa.gov/oact/babynames/names.zip"
MIRROR_URL = "https://api.github.com/repos/askbloom/popular-baby-name-ranking-trends/contents/raw/year"
OUTPUT = Path(__file__).with_name("ssa-baby-names.csv")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def download_from_mirror():
    files = json.loads(fetch(MIRROR_URL))
    yearly_files = sorted(
        (
            item
            for item in files
            if re.fullmatch(r"yob\d{4}\.txt", item["name"])
        ),
        key=lambda item: int(item["name"][3:7]),
    )
    if not yearly_files:
        raise ValueError("The public mirror contains no yearly name data.")

    def download_file(item):
        return item["name"], fetch(item["download_url"]).decode("utf-8")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(download_file, yearly_files))


def main():
    try:
        archive_data = fetch(URL)
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise
        print("SSA returned HTTP 403; downloading yearly data from a public mirror.", file=sys.stderr)
        yearly_data = download_from_mirror()
    else:
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            yearly_files = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"yob\d{4}\.txt", name)),
                key=lambda name: int(name[3:7]),
            )
            if not yearly_files:
                raise ValueError("The downloaded archive contains no yearly name data.")
            yearly_data = [
                (filename, archive.read(filename).decode("utf-8"))
                for filename in yearly_files
            ]

    with OUTPUT.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["year", "name", "sex", "count"])
        for filename, data in yearly_data:
            year = int(filename[3:7])
            for name, sex, count in csv.reader(io.StringIO(data, newline="")):
                writer.writerow([year, name, sex, count])

    print(f"Created {OUTPUT} with data for {len(yearly_data)} years.")


if __name__ == "__main__":
    main()
