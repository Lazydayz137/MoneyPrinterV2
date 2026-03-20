import os
import io
import re
import csv
import time
import glob
import shlex
import zipfile
import yagmail
import requests
import subprocess
import platform

from cache import *
from status import *
from config import *
from llm_provider import generate_text

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    import resend
except ImportError:
    resend = None



class Outreach:
    """
    Class that houses the methods to reach out to businesses.
    """

    def __init__(self) -> None:
        """
        Constructor for the Outreach class.

        Returns:
            None
        """
        # Check if go is installed
        self.go_installed = os.system("go version") == 0

        # Set niche
        self.niche = get_google_maps_scraper_niche()

        # Set email credentials
        self.email_creds = get_email_credentials()

    def _find_scraper_dir(self) -> str:
        candidates = sorted(glob.glob("google-maps-scraper-*"))
        for candidate in candidates:
            if os.path.isdir(candidate) and os.path.exists(
                os.path.join(candidate, "go.mod")
            ):
                return candidate
        return ""

    def is_go_installed(self) -> bool:
        """
        Check if go is installed.

        Returns:
            bool: True if go is installed, False otherwise.
        """
        # Check if go is installed
        try:
            subprocess.call(["go", "version"])
            return True
        except Exception as e:
            return False

    def unzip_file(self, zip_link: str) -> None:
        """
        Unzip the file.

        Args:
            zip_link (str): The link to the zip file.

        Returns:
            None
        """
        if self._find_scraper_dir():
            info("=> Scraper already unzipped. Skipping unzip.")
            return

        r = requests.get(zip_link)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for member in z.namelist():
            if ".." in member or member.startswith("/"):
                warning(f"Skipping suspicious path in archive: {member}")
                continue
            z.extract(member)

    def build_scraper(self) -> None:
        """
        Build the scraper.

        Returns:
            None
        """
        binary_name = (
            "google-maps-scraper.exe"
            if platform.system() == "Windows"
            else "google-maps-scraper"
        )
        if os.path.exists(binary_name):
            print(colored("=> Scraper already built. Skipping build.", "blue"))
            return

        scraper_dir = self._find_scraper_dir()
        if not scraper_dir:
            raise FileNotFoundError(
                "Could not locate extracted google-maps-scraper directory."
            )

        subprocess.run(["go", "mod", "download"], cwd=scraper_dir, check=True)
        subprocess.run(["go", "build"], cwd=scraper_dir, check=True)

        built_binary = os.path.join(scraper_dir, binary_name)
        if not os.path.exists(built_binary):
            raise FileNotFoundError(f"Expected built scraper binary at: {built_binary}")

        os.replace(built_binary, binary_name)

    def run_scraper_with_args_for_30_seconds(self, args: str, timeout=300) -> None:
        """
        Run the scraper with the specified arguments for 30 seconds.

        Args:
            args (str): The arguments to run the scraper with.
            timeout (int): The time to run the scraper for.

        Returns:
            None
        """
        info(" => Running scraper...")
        binary_name = (
            "google-maps-scraper.exe"
            if platform.system() == "Windows"
            else "google-maps-scraper"
        )
        command = [os.path.join(os.getcwd(), binary_name)] + shlex.split(args)
        try:
            scraper_process = subprocess.run(command, timeout=float(timeout))

            if scraper_process.returncode == 0:
                print(colored("=> Scraper finished successfully.", "green"))
            else:
                print(colored("=> Scraper finished with an error.", "red"))
        except subprocess.TimeoutExpired:
            print(colored("=> Scraper timed out.", "red"))
        except Exception as e:
            print(colored("An error occurred while running the scraper:", "red"))
            print(str(e))

    def get_items_from_file(self, file_name: str) -> list:
        """
        Read and return items from a file.

        Args:
            file_name (str): The name of the file to read from.

        Returns:
            list: The items from the file.
        """
        # Read and return items from a file
        with open(file_name, "r", errors="ignore") as f:
            items = f.readlines()
            items = [item.strip() for item in items[1:]]
            return items

    def set_email_for_website(self, index: int, website: str, output_file: str):
        """Extracts an email address from a website and updates a CSV file with it.

        This method sends a GET request to the specified website, searches for the
        first email address in the HTML content, and appends it to the specified
        row in a CSV file. If no email address is found, no changes are made to
        the CSV file.

        Args:
            index (int): The row index in the CSV file where the email should be appended.
            website (str): The URL of the website to extract the email address from.
            output_file (str): The path to the CSV file to update with the extracted email."""
        # Extract and set an email for a website
        email = ""

        r = requests.get(website)
        if r.status_code == 200:
            # Define a regular expression pattern to match email addresses
            email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"

            # Find all email addresses in the HTML string
            email_addresses = re.findall(email_pattern, r.text)

            email = email_addresses[0] if len(email_addresses) > 0 else ""

        if email:
            print(f"=> Setting email {email} for website {website}")
            with open(output_file, "r", newline="", errors="ignore") as csvfile:
                csvreader = csv.reader(csvfile)
                items = list(csvreader)
                items[index].append(email)

            with open(output_file, "w", newline="", errors="ignore") as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(items)


    def start(self) -> None:
        """
        Start the outreach process.
        """
        scraper_choice = get_outreach_scraper()
        email_provider = get_email_provider()

        output_path = get_results_cache_path()
        message_subject = get_outreach_message_subject()
        message_body = get_outreach_message_body_file()

        if scraper_choice == "playwright" and sync_playwright:
            info(" => Using Playwright to scrape Google Maps data...")
            items = []
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=get_headless())
                page = browser.new_page()
                page.goto(f"https://www.google.com/maps/search/{self.niche.replace(' ', '+')}", timeout=60000)
                time.sleep(5) # Wait for results

                # Extremely simplified scraping for demonstration
                # A real maps scraper is complex and requires scrolling
                elements = page.query_selector_all("a[href^='http']")
                for el in elements[:10]:
                    link = el.get_attribute("href")
                    if link and "google.com" not in link:
                        items.append(f"FoundBusiness,,,{link}")
                browser.close()

            success(f" => Scraped {len(items)} potential links.")
            # Mock writing to output file
            with open(output_path, "w") as f:
                f.write("Name,Address,Phone,Website\n")
                for item in items:
                    f.write(f"{item}\n")
        else:
            # Check if go is installed
            if not self.is_go_installed():
                error("Go is not installed. Please install go and try again.")
                return

            # Unzip the scraper
            self.unzip_file(get_google_maps_scraper_zip_url())

            # Build the scraper
            self.build_scraper()

            # Write the niche to a file
            with open("niche.txt", "w") as f:
                f.write(self.niche)

            # Run
            self.run_scraper_with_args_for_30_seconds(
                f'-input niche.txt -results "{output_path}"', timeout=get_scraper_timeout()
            )

            if not os.path.exists(output_path):
                error(
                    f" => Scraper output not found at {output_path}. Check scraper logs and configuration."
                )
                if os.path.exists("niche.txt"): os.remove("niche.txt")
                return

            # Get the items from the file
            items = self.get_items_from_file(output_path)
            success(f" => Scraped {len(items)} items.")

            # Remove the niche file
            if os.path.exists("niche.txt"): os.remove("niche.txt")

        time.sleep(2)

        yag = None
        if email_provider == "smtp":
            yag = yagmail.SMTP(
                user=self.email_creds["username"],
                password=self.email_creds["password"],
                host=self.email_creds["smtp_server"],
                port=self.email_creds["smtp_port"],
            )
        elif email_provider == "resend" and resend:
            resend.api_key = get_resend_api_key()
            if not resend.api_key:
                error("Resend API key is missing.")
                return

        # Get the email for each business
        for index, item in enumerate(items, start=1):
            try:
                # Check if the item"s website is valid
                parts = item.split(",")
                website = [w for w in parts if w.startswith("http")]
                website = website[0] if len(website) > 0 else ""

                receiver_email = parts[-1] if "@" in parts[-1] else ""

                if website != "" and not receiver_email:
                    test_r = requests.get(website)
                    if test_r.status_code == 200:
                        self.set_email_for_website(index, website, output_path)

                        # Re-read to get updated email if found
                        with open(output_path, "r") as f:
                            lines = f.readlines()
                            if len(lines) > index:
                                updated_parts = lines[index].strip().split(",")
                                if "@" in updated_parts[-1]:
                                    receiver_email = updated_parts[-1]

                if not receiver_email or "@" not in receiver_email:
                    warning(f" => No email provided/found for {website}. Skipping...")
                    continue

                company_name = parts[0] if len(parts) > 0 else "there"

                # Optionally use LLM to personalize the body
                base_body = open(message_body, "r").read() if os.path.exists(message_body) else "Hello {{COMPANY_NAME}},\n\nI\'d like to work with you."

                if get_llm_provider():
                    try:
                        info(f" => Generating personalized email body for {company_name}...")
                        prompt = f"Rewrite this cold outreach email to be highly personalized for a company named '{company_name}' whose website is '{website}'. Base Template: {base_body}"
                        personalized_body = generate_text(prompt)
                    except Exception as e:
                        error(f"Failed to personalize with LLM: {e}")
                        personalized_body = base_body.replace("{{COMPANY_NAME}}", company_name)
                else:
                    personalized_body = base_body.replace("{{COMPANY_NAME}}", company_name)

                subject = message_subject.replace("{{COMPANY_NAME}}", company_name)

                info(f" => Sending email to {receiver_email}...")

                if email_provider == "resend" and resend:
                    r = resend.Emails.send({
                        "from": "onboarding@resend.dev", # Need a verified domain in reality
                        "to": receiver_email,
                        "subject": subject,
                        "html": personalized_body
                    })
                    success(f" => Sent email to {receiver_email} via Resend: {r}")
                elif yag:
                    yag.send(
                        to=receiver_email,
                        subject=subject,
                        contents=personalized_body,
                    )
                    success(f" => Sent email to {receiver_email} via SMTP")

            except Exception as err:
                error(f" => Error processing item: {err}...")
                continue
