
import os
import time
from urllib.parse import urlparse
from typing import Any

from status import *
from config import *
from constants import *
from llm_provider import generate_text
from .Twitter import Twitter
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from selenium import webdriver

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None



class AffiliateMarketing:
    """
    This class will be used to handle all the affiliate marketing related operations.
    """

    def __init__(
        self,
        affiliate_link: str,
        fp_profile_path: str,
        twitter_account_uuid: str,
        account_nickname: str,
        topic: str,
    ) -> None:
        """
        Initializes the Affiliate Marketing class.

        Args:
            affiliate_link (str): The affiliate link
            fp_profile_path (str): The path to the Firefox profile
            twitter_account_uuid (str): The Twitter account UUID
            account_nickname (str): The account nickname
            topic (str): The topic of the product

        Returns:
            None
        """
        self._fp_profile_path: str = fp_profile_path

        # Initialize the Firefox profile
        self.options: Options = Options()

        # Set headless state of browser
        if get_headless():
            self.options.add_argument("--headless")

        if not os.path.isdir(fp_profile_path):
            raise ValueError(
                f"Firefox profile path does not exist or is not a directory: {fp_profile_path}"
            )

        # Set the profile path
        self.options.add_argument("-profile")
        self.options.add_argument(fp_profile_path)

        # Set the service
        self.service: Service = Service(GeckoDriverManager().install())

        # Initialize the browser
        self.browser: webdriver.Firefox = webdriver.Firefox(
            service=self.service, options=self.options
        )

        # Set the affiliate link
        self.affiliate_link: str = affiliate_link

        parsed_link = urlparse(self.affiliate_link)
        if parsed_link.scheme not in ["http", "https"] or not parsed_link.netloc:
            raise ValueError(
                f"Affiliate link is invalid. Expected a full URL, got: {self.affiliate_link}"
            )

        # Set the Twitter account UUID
        self.account_uuid: str = twitter_account_uuid

        # Set the Twitter account nickname
        self.account_nickname: str = account_nickname

        # Set the Twitter topic
        self.topic: str = topic

        # Scrape the product information
        self.scrape_product_information()


    def scrape_product_information(self) -> None:
        """
        This method will be used to scrape the product
        information from the affiliate link using Playwright for better bypass.
        """
        scraper = get_outreach_scraper()

        if scraper == "playwright" and sync_playwright:
            if get_verbose():
                info("Using Playwright to scrape Amazon product...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=get_headless())
                page = browser.new_page()
                page.goto(self.affiliate_link, timeout=60000)
                time.sleep(3) # wait for page to render

                try:
                    product_title = page.locator("#productTitle").text_content()
                except Exception:
                    product_title = page.title()

                try:
                    features_list = page.locator("#feature-bullets").text_content()
                except Exception:
                    features_list = "Product features not found via playwright."

                browser.close()

            self.product_title = product_title.strip() if product_title else "Unknown Title"
            self.features = features_list.strip() if features_list else "No features listed"

        else:
            if get_verbose():
                info("Using Selenium to scrape Amazon product...")
            # Open the affiliate link
            self.browser.get(self.affiliate_link)

            try:
                product_title = self.browser.find_element(
                    By.ID, AMAZON_PRODUCT_TITLE_ID
                ).text
            except Exception:
                product_title = self.browser.title

            try:
                features = self.browser.find_element(By.ID, AMAZON_FEATURE_BULLETS_ID).text
            except Exception:
                features = "Product features not found via selenium."

            self.product_title = product_title
            self.features = features

        if get_verbose():
            info(f"Product Title: {self.product_title}")
            info(f"Features: {self.features}")


    def generate_response(self, prompt: str) -> str:
        """
        This method will be used to generate the response for the user.

        Args:
            prompt (str): The prompt for the user.

        Returns:
            response (str): The response for the user.
        """
        return generate_text(prompt)

    def generate_pitch(self) -> str:
        """
        This method will be used to generate a pitch for the product.

        Returns:
            pitch (str): The pitch for the product.
        """
        # Generate the response
        pitch: str = (
            self.generate_response(
                f'I want to promote this product on my website. Generate a brief pitch about this product, return nothing else except the pitch. Information:\nTitle: "{self.product_title}"\nFeatures: "{str(self.features)}"'
            )
            + "\nYou can buy the product here: "
            + self.affiliate_link
        )

        self.pitch: str = pitch

        # Return the response
        return pitch

    def share_pitch(self, where: str) -> None:
        """
        This method will be used to share the pitch on the specified platform.

        Args:
            where (str): The platform where the pitch will be shared.
        """
        if where == "twitter":
            # Initialize the Twitter class
            twitter: Twitter = Twitter(
                self.account_uuid,
                self.account_nickname,
                self._fp_profile_path,
                self.topic,
            )

            # Share the pitch
            twitter.post(self.pitch)

    def quit(self) -> None:
        """
        This method will be used to quit the browser.
        """
        # Quit the browser
        self.browser.quit()
