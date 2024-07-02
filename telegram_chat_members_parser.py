import sys
import os
from datetime import datetime
import logging
import json
import configparser

from typing import List, Dict


class Parser:
    def __init__(self, config_file="config.ini"):
        self.txt_name = sys.argv[1]
        self.txt_path = os.getcwd() + "/src/" + self.txt_name
        self.db_name = self.txt_name.split(".")[0]

        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        self._username = self.config["Telegram"]["username"]
        self._api_id = self.config["Telegram"]["api_id"]
        self._api_hash = self.config["Telegram"]["api_hash"]

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.console_handler = logging.StreamHandler()
        self.console_handler.setLevel(logging.INFO)

        self.file_handler = logging.FileHandler("logs/parser.log")
        self.file_handler.setLevel(logging.INFO)

        self.formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        self.console_handler.setFormatter(self.formatter)
        self.file_handler.setFormatter(self.formatter)

        self.logger.addHandler(self.console_handler)
        self.logger.addHandler(self.file_handler)

    def get_chats(self) -> List[str]:
        try:
            with open(self.txt_path, "r") as f:
                txt_data = f.read()

        except FileNotFoundError:
            self.logger.error(f"File \"{self.txt_path}\" not found")
            sys.exit(1)

        try:
            chats = txt_data.split("\n")
            chats = [chat for chat in chats if chat]

        except Exception as ex:
            self.logger.error(f"Error while parsing chats, details: {ex}")
            sys.exit(1)

        else:
            self.logger.info(f"Parsed chats: {', '.join(chats)}")

        return chats

    def get_members(self) -> List[Dict]:
        # TODO
        pass

    def get_db_data(self) -> Dict:
        try:
            db_name = self.db_name
            members = self.get_members()
            members_count = len(members)
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            from_chats = self.get_chats()

            db_data = {
                "db_name": db_name,
                "created_at": created_at,
                "members_count": members_count,
                "from_chats": from_chats,
                "members": members
            }

        except Exception as ex:
            self.logger.error(f"Error while collecting database, details: {ex}")
            sys.exit(1)

        else:
            self.logger.info("Database collected")
            self.logger.info(f"Members in database: {members_count}")

        return db_data

    def create_db(self) -> str:
        try:
            db_data = self.get_db_data()
            db_data_json = json.dumps(db_data, indent=4)

            with open(f"results/{self.db_name}.json", "w", encoding="utf-8") as f:
                f.write(db_data_json)

            db_path = os.getcwd() + "/results/" + self.db_name + ".json"

        except Exception as ex:
            self.logger.error(f"Error while creating database, details: {ex}")
            sys.exit(1)

        else:
            self.logger.info(f"Database created: {db_path}")

        return db_path
