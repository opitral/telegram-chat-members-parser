import os
import sys
from datetime import datetime
import asyncio
import logging
import configparser
import sqlite3

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


def get_chats(txt_name: str) -> List[str]:
    txt_path = os.path.join(os.getcwd(), "src", f"{txt_name}.txt")
    os.makedirs(os.path.dirname(txt_path), exist_ok=True)

    try:
        with open(txt_path, "r") as f:
            file_data = f.read()

        chats = file_data.split("\n")
        chats = [chat.strip() for chat in chats if chat and not chat.startswith("#")]

    except FileNotFoundError:
        logger.error(f"File \"{txt_path}\" not found")
        sys.exit(1)

    except Exception as ex:
        logger.error(f"Error while receiving chats, details: {ex}")
        sys.exit(1)

    else:
        logger.info(f"Chats received: {', '.join(chats)}")
        return chats


def create_db(db_name: str, target_chats: List[str]) -> str:
    try:
        db_path = os.path.join(os.getcwd(), "results", f"{db_name}.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        if os.path.isfile(db_path):
            logger.error(f"Database with the name \"{db_name}\" already exists")
            sys.exit(1)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS target_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_link VARCHAR(255) NOT NULL,
                members_count INTEGER DEFAULT 0 NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                phone_number VARCHAR(255),
                target_chat_id INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'awaits' NOT NULL,
                FOREIGN KEY (target_chat_id) REFERENCES target_chats(id)
            )
        ''')

        for chat_link in target_chats:
            cursor.execute('''
                INSERT INTO target_chats (chat_link) 
                VALUES (?)
            ''', (chat_link,))

        conn.commit()
        conn.close()

    except Exception as ex:
        logger.error(f"Error while creating database, details: {ex}")
        sys.exit(1)

    else:
        logger.info(f"Database created: {db_path}")
        return db_path


def update_db(db_name: str, member: Dict):
    try:
        db_path = os.path.join(os.getcwd(), "results", f"{db_name}.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO members (telegram_id, username, first_name, last_name, phone_number, target_chat_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''',
                       (
                           member["telegram_id"],
                           member["username"],
                           member["first_name"],
                           member["last_name"],
                           member["phone_number"],
                           member["target_chat_id"]
                       )
                       )

        cursor.execute('''
            UPDATE target_chats
            SET members_count = members_count + 1
            WHERE id = ?
        ''', (member["target_chat_id"],))

        cursor.execute("SELECT COUNT(*) FROM members")
        total_members_count = cursor.fetchone()[0]

        conn.commit()
        conn.close()

    except Exception as ex:
        logger.error(f"Error while updating database, details: {ex}")

    else:
        logger.info(f"Database updated with total: {total_members_count}")


async def main():
    db_name = sys.argv[1]
    target_chats_list = get_chats(db_name)
    db_path = create_db(db_name, target_chats_list)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    current_chat = None
    await bot.start()

    try:
        account = await bot.get_me()
        current_datetime = datetime.now()

        cursor.execute('SELECT id, chat_link FROM target_chats')
        target_chats = cursor.fetchall()

        for chat in target_chats:
            try:
                current_chat = await bot.join_chat(chat[1])
                logger.info(f"Joined chat: {chat[1]}")

                logger.info("Parsing type: list")
                async for member in bot.get_chat_members(current_chat.id):
                    try:
                        if (member.user.is_bot or
                                member.user.is_deleted or
                                member.status == ChatMemberStatus.OWNER or
                                member.user.id == account.id or
                                member.user.status == UserStatus.LONG_AGO):
                            continue

                        cursor.execute("SELECT * FROM members WHERE telegram_id = ?", (member.user.id,))
                        found_lead = cursor.fetchone()

                        if found_lead:
                            continue

                        lead = {
                            "telegram_id": member.user.id,
                            "username": member.user.username,
                            "first_name": member.user.first_name,
                            "last_name": member.user.last_name,
                            "phone_number": member.user.phone_number,
                            "target_chat_id": chat[0]
                        }

                        update_db(db_name, lead)
                        logger.info(lead)

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
                                message.from_user.id == account.id or
                                message.from_user.status == UserStatus.LONG_AGO or
                                message.sender_chat):
                            continue

                        cursor.execute("SELECT * FROM members WHERE telegram_id = ?", (message.from_user.id,))
                        found_lead = cursor.fetchone()

                        if found_lead:
                            continue

                        lead = {
                            "telegram_id": message.from_user.id,
                            "username": message.from_user.username,
                            "first_name": message.from_user.first_name,
                            "last_name": message.from_user.last_name,
                            "phone_number": message.from_user.phone_number,
                            "target_chat_id": chat[0]
                        }

                        update_db(db_name, lead)
                        logger.info(lead)

                    except Exception as ex:
                        logger.error(f"Error parsing messages {message}, details: {ex}")
                        continue

                cursor.execute("SELECT members_count FROM target_chats WHERE id = ?", (chat[0],))
                current_chat_members_count = cursor.fetchone()[0]
                logger.info(f"From {chat[1]} received members: {current_chat_members_count}")

            except Exception as ex:
                logger.error(f"Error parsing members, details: {ex}")
                continue

            finally:
                try:
                    await bot.leave_chat(current_chat.id)

                except Exception as ex:
                    logger.error(ex)
                    logger.warning(f"Account was banned in: {chat[1]}")

                else:
                    logger.info(f"Leaved chat: {chat[1]}")

    except Exception as ex:
        logger.error(ex)

    finally:
        conn.close()
        await bot.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
