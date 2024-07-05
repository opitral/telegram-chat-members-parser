import json
import os
import sys
from datetime import datetime
import asyncio
import logging
import configparser

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus, UserStatus

from typing import List, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("parser.log")
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

config = configparser.ConfigParser()
config.read("config.ini")

session = config["Telegram"]["session"]
api_id = config["Telegram"]["api_id"]
api_hash = config["Telegram"]["api_hash"]

bot = Client(session, api_id, api_hash)
logger.info(f"Session started: {session}")


def get_chats(file_path: str) -> List[str]:
    try:
        with open(file_path, "r") as f:
            file_data = f.read()

        chats = file_data.split("\n")
        chats = [chat for chat in chats if chat]
        chats = [chat for chat in chats if not chat.startswith("#")]

    except FileNotFoundError:
        logger.error(f"File \"{file_path}\" not found")
        sys.exit(1)

    except Exception as ex:
        logger.error(f"Error while receiving chats, details: {ex}")
        sys.exit(1)

    else:
        logger.info(f"Chats received: {', '.join(chats)}")
        return chats


def create_db(db_name: str, targeted_chats: List[str]) -> str:
    try:
        db_data = {
            "db_name": db_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "members_count": 0,
            "from_chats": targeted_chats,
            "members": []
        }

        with open(f"results/{db_name}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(db_data, indent=4, ensure_ascii=False))

        db_path = os.getcwd() + "/results/" + db_name + ".json"

    except Exception as ex:
        logger.error(f"Error while creating database, details: {ex}")
        sys.exit(1)

    else:
        logger.info(f"Database created: {db_path}")
        return db_path


def update_db(db_name: str, members: List[Dict]) -> int:
    try:
        with open(f"results/{db_name}.json", "r", encoding="utf-8") as f:
            db_data = f.read()

        db_data_obj = json.loads(db_data)

        members_list_new = db_data_obj["members"] + members

        db_data_new = {
            "db_name": db_data_obj["db_name"],
            "created_at": db_data_obj["created_at"],
            "members_count": len(members_list_new),
            "from_chats": db_data_obj["from_chats"],
            "members": members_list_new
        }

        with open(f"results/{db_name}.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(db_data_new, indent=4, ensure_ascii=False))

    except Exception as ex:
        logger.error(f"Error while updating database, details: {ex}")

    else:
        logger.info(f"Database updated with total: {len(members_list_new)}")
        return len(members_list_new)


async def main():
    txt_name = sys.argv[1]
    txt_path = os.getcwd() + "/src/" + txt_name
    db_name = txt_name.split(".")[0]

    targeted_chats = get_chats(txt_path)
    create_db(db_name, targeted_chats)

    current_chat = None
    tg_lead_ids = []
    lead_id = 1

    await bot.start()

    try:
        my_account = await bot.get_me()
        current_datetime = datetime.now()
        for chat_link in targeted_chats:
            try:
                current_chat_members = []
                current_chat_members_count = 0
                current_chat = await bot.join_chat(chat_link)
                logger.info(f"Joined chat: {chat_link}")

                logger.info("Parsing type: list")
                async for member in bot.get_chat_members(current_chat.id):
                    try:
                        if (member.user.is_bot or
                                member.user.is_deleted or
                                member.status == ChatMemberStatus.OWNER or
                                member.status == ChatMemberStatus.ADMINISTRATOR or
                                member.user.id in tg_lead_ids or
                                member.user.id == my_account.id or
                                member.user.status == UserStatus.LONG_AGO):
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

                        tg_lead_ids.append(lead["telegram_id"])
                        current_chat_members.append(lead)
                        lead_id += 1
                        current_chat_members_count += 1
                        logger.info(lead)

                        if len(current_chat_members) % 100 == 0:
                            update_db(db_name, current_chat_members)
                            current_chat_members.clear()

                    except Exception as ex:
                        logger.error(f"Error parsing list {member}, details: {ex}")
                        continue

                logger.info("Parsing type: messages")
                async for message in bot.get_chat_history(current_chat.id):
                    try:
                        date_difference = current_datetime - message.date
                        if date_difference.days >= 90:
                            break

                        if (message.from_user.is_bot or
                                message.from_user.is_deleted or
                                message.from_user.id in tg_lead_ids or
                                message.from_user.id == my_account.id or
                                message.from_user.status == UserStatus.LONG_AGO):
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

                        tg_lead_ids.append(lead["telegram_id"])
                        current_chat_members.append(lead)
                        lead_id += 1
                        current_chat_members_count += 1
                        logger.info(lead)

                        if len(current_chat_members) % 100 == 0:
                            update_db(db_name, current_chat_members)
                            current_chat_members.clear()

                    except Exception as ex:
                        logger.error(f"Error parsing messages {message}, details: {ex}")
                        continue

                if current_chat_members:
                    logger.info(f"From {chat_link} received members: {current_chat_members_count}")
                    update_db(db_name, current_chat_members)

            except Exception as ex:
                logger.error(f"Error parsing members, details: {ex}")
                continue

            finally:
                if current_chat:
                    await bot.leave_chat(current_chat.id)
                    logger.info(f"Leaved chat: {chat_link}")

    finally:
        await bot.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
