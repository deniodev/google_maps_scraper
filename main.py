from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys

@dataclass
class Business:
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    business_list: list[Business] = field(default_factory=list)
    save_at = 'output'

    def dataframe(self):
        return pd.json_normalize((asdict(b) for b in self.business_list), sep="_")

    def save_to_excel(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    coords = url.split('/@')[-1].split('/')[0].split(',')
    return float(coords[0]), float(coords[1])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    if args.search:
        search_list = [args.search]
    else:
        input_file = 'input.txt'
        if os.path.exists(input_file):
            with open(input_file, 'r', encoding='utf-8') as f:
                search_list = [line.strip() for line in f if line.strip()]
        else:
            print('Erro: passe -s ou preencha input.txt')
            sys.exit(1)

    total = args.total or 1000000

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)

        for idx, term in enumerate(search_list):
            print(f"-----\n{idx} - {term}")
            page.locator('//input[@id="searchboxinput"]').fill(term)
            page.wait_for_timeout(3000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            panel = page.locator('div.section-layout.section-scrollbox')
            if panel.count() == 0:
                panel = page.locator('div[role="feed"]')

            # Nova rolagem inteligente
            previous_count = -1
            same_count_tries = 0
            max_tries = 10

            while True:
                handle = panel.element_handle()
                page.evaluate('(p) => p.scrollBy(0, 1000)', handle)
                page.wait_for_timeout(1500)

                current_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()

                if current_count == previous_count:
                    same_count_tries += 1
                else:
                    same_count_tries = 0

                if same_count_tries >= max_tries or current_count >= total:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                    print(f"Total Scraped: {len(listings)}")
                    break

                previous_count = current_count
                print(f"Currently Scraped: {current_count}")

            business_list = BusinessList()

            name_attr = 'aria-label'
            address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
            website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
            phone_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
            review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
            review_avg_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

            for listing in listings:
                try:
                    listing.click(timeout=10000)
                    page.wait_for_timeout(7000)
                    biz = Business()
                    raw = listing.get_attribute(name_attr)
                    biz.name = raw or ""

                    if page.locator(address_xpath).count():
                        biz.address = page.locator(address_xpath).first.inner_text().strip() or ""
                    if page.locator(website_xpath).count():
                        biz.website = page.locator(website_xpath).first.inner_text().strip() or ""
                    if page.locator(phone_xpath).count():
                        biz.phone_number = page.locator(phone_xpath).first.inner_text().strip() or ""

                    if page.locator(review_count_xpath).count():
                        text = page.locator(review_count_xpath).inner_text().strip()
                        biz.reviews_count = int(text.split()[0].replace(',', '')) if text else 0
                    else:
                        biz.reviews_count = 0

                    if page.locator(review_avg_xpath).count():
                        avg = page.locator(review_avg_xpath).get_attribute(name_attr)
                        biz.reviews_average = float(avg.split()[0].replace(',', '.')) if avg else 0.0
                    else:
                        biz.reviews_average = 0.0

                    biz.latitude, biz.longitude = extract_coordinates_from_url(page.url)
                    business_list.business_list.append(biz)
                except Exception as e:
                    print(f"Erro ao extrair empresa: {e}")

            safe = term.replace(' ', '_')
            business_list.save_to_excel(f"google_maps_data_{safe}")
            business_list.save_to_csv(f"google_maps_data_{safe}")

        browser.close()

if __name__ == "__main__":
    main()
