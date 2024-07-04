import sys
import os
from datetime import datetime
import logging
import json
import configparser

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus

from typing import List, Dict


class Parser:
    def __init__(self, config_file="config.ini"):
        self.txt_name = sys.argv[1]
        self.txt_path = os.getcwd() + "/src/" + self.txt_name
        self.db_name = self.txt_name.split(".")[0]

        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        self.session = self.config["Telegram"]["session"]
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

        self.bot = Client(self.session, self._api_id, self._api_hash)
        self.logger.info(f"Session started: {self.session}")

        self.from_chats = self.get_chats()

        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

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
            chats = [chat for chat in chats if not chat.startswith("#")]

        except Exception as ex:
            self.logger.error(f"Error while receiving chats, details: {ex}")
            sys.exit(1)

        else:
            self.logger.info(f"Chats received: {', '.join(chats)}")

        return chats

    async def get_members(self) -> List[Dict]:
        tg_lead_ids = []
        my_account = await self.bot.get_me()
        lead_id = 1
        members = []
        chat_in_progress_id = None

        for chat_link in self.from_chats:
            try:
                self.logger.info(f"Parsing chat: {chat_link}")

                chat = await self.bot.join_chat(chat_link)
                chat_in_progress_id = chat.id
                self.logger.info(f"Joined chat: {chat_link}")

                self.logger.info("Parsing type: list")
                async for member in self.bot.get_chat_members(chat.id):
                    try:
                        if (member.user.is_bot or
                                member.user.is_deleted or
                                member.status == ChatMemberStatus.OWNER or
                                member.status == ChatMemberStatus.ADMINISTRATOR or
                                member.user.id in tg_lead_ids or
                                member.user.id == my_account.id):
                            continue

                        lead = {
                            "id": lead_id,
                            "telegram_id": member.user.id,
                            "username": member.user.username,
                            "first_name": member.user.first_name,
                            "last_name": member.user.last_name,
                            "phone_number": member.user.phone_number,
                            "from_chat": chat_link,
                            "status": "awaits"
                        }

                        lead_id += 1
                        tg_lead_ids.append(lead["telegram_id"])
                        members.append(lead)

                        self.logger.info(lead)

                    except Exception as ex:
                        self.logger.error(f"Error parsing member {member}, details: {ex}")
                        continue

                if len(members) == 0:
                    self.logger.info("Parsing type: messages")
                    async for message in self.bot.get_chat_history(chat.id):
                        try:
                            if len(members) % 100 == 0:
                                self.save_members(members)

                            if (message.from_user.is_bot or
                                    message.from_user.is_deleted or
                                    message.from_user.id in tg_lead_ids or
                                    message.from_user.id == my_account.id):
                                continue

                            lead = {
                                "id": lead_id,
                                "telegram_id": message.from_user.id,
                                "username": message.from_user.username,
                                "first_name": message.from_user.first_name,
                                "last_name": message.from_user.last_name,
                                "phone_number": message.from_user.phone_number,
                                "from_chat": chat_link,
                                "status": "awaits"
                            }

                            lead_id += 1
                            tg_lead_ids.append(lead["telegram_id"])
                            members.append(lead)

                            self.logger.info(lead)

                        except Exception as ex:
                            self.logger.error(f"Error parsing message {message}, details: {ex}")
                            continue

            except Exception as ex:
                self.logger.error(f"Error fetching members from {chat_link}, details: {ex}")

            finally:
                await self.bot.leave_chat(chat_in_progress_id)
                self.logger.info(f"Leaved chat: {chat_link}")

        return members

    async def get_db_data(self) -> Dict:
        try:
            await self.bot.start()

            db_name = self.db_name
            members = await self.get_members()
            members_count = len(members)
            created_at = self.created_at
            from_chats = self.from_chats

            await self.bot.stop()

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
            self.logger.info("Database collection complete")
            self.logger.info(f"Members in database: {members_count}")

        return db_data

    async def create_db(self):
        try:
            db_data = await self.get_db_data()
            db_data_json = json.dumps(db_data, indent=4, ensure_ascii=False)

            with open(f"results/{self.db_name}.json", "w", encoding="utf-8") as f:
                f.write(db_data_json)

            db_path = os.getcwd() + "/results/" + self.db_name + ".json"

        except Exception as ex:
            self.logger.error(f"Error while creating database, details: {ex}")
            sys.exit(1)

        else:
            self.logger.info(f"Database created: {db_path}")

    def save_members(self, members):
        try:
            db_name = self.db_name
            members_count = len(members)
            created_at = self.created_at
            from_chats = self.from_chats

            db_data = {
                "db_name": db_name,
                "created_at": created_at,
                "members_count": members_count,
                "from_chats": from_chats,
                "members": members
            }

            db_data_json = json.dumps(db_data, indent=4, ensure_ascii=False)

            with open(f"results/{self.db_name}.json", "w", encoding="utf-8") as f:
                f.write(db_data_json)

            db_path = os.getcwd() + "/results/" + self.db_name + ".json"

            self.logger.info(f"Database saved: {db_path}")

        except Exception as ex:
            self.logger.error(f"Error while saving database, details: {ex}")
            sys.exit(1)
