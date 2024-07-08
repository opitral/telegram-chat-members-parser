import os
import sys
import time
from datetime import datetime
import asyncio
import logging
import configparser
import sqlite3

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus, UserStatus
from pyrogram.errors import UserAlreadyParticipant, UserNotParticipant, FloodWait
from pyrogram.types import Chat

from typing import List, Dict


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("parser.log")
file_handler.setLevel(logging.WARNING)

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
history_period = config["Parser"]["history_period"]

bot = Client(session, api_id, api_hash)
logger.info(f"Session started: {session}")


def format_seconds(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"


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


def create_db(db_name: str, from_chats: List[str]) -> str:
    try:
        db_path = os.path.join(os.getcwd(), "results", f"{db_name}.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        if os.path.isfile(db_path):
            logger.error(f"Database with the name \"{db_name}\" already exists")
            sys.exit(1)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS from_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link VARCHAR(255) NOT NULL,
                members INTEGER DEFAULT 0 NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                phone VARCHAR(255),
                photo INTEGER,
                premium INTEGER,
                from_chat_id INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'free' NOT NULL,
                FOREIGN KEY (from_chat_id) REFERENCES from_chats(id)
            )
        ''')

        for link in from_chats:
            cursor.execute('''
                INSERT INTO from_chats (link) 
                VALUES (?)
            ''', (link,))

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
            INSERT INTO members (telegram_id, username, first_name, last_name, phone, photo, premium, from_chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
                       (
                           member["telegram_id"],
                           member["username"],
                           member["first_name"],
                           member["last_name"],
                           member["phone"],
                           member["photo"],
                           member["premium"],
                           member["from_chat_id"]
                       )
                       )

        cursor.execute('''
            UPDATE from_chats
            SET members = members + 1
            WHERE id = ?
        ''', (member["from_chat_id"],))

        cursor.execute("SELECT COUNT(*) FROM members")
        total_members_count = cursor.fetchone()[0]

        conn.commit()
        conn.close()

    except Exception as ex:
        logger.error(f"Error while updating database, details: {ex}")

    else:
        logger.info(f"Database updated with total: {total_members_count}")


async def join_chat(link: str) -> Chat:
    try:
        chat = await bot.join_chat(link)
        logger.info(f"Joined chat: {link}")
        return chat

    except UserAlreadyParticipant:
        logger.info(f"Already participant: {link}")
        chat = await bot.get_chat(link)
        return chat

    except FloodWait as e:
        logger.warning(f"Flood wait: {e.value} seconds")
        await asyncio.sleep(e.value)


async def main():
    db_name = sys.argv[1]
    from_chats_list = get_chats(db_name)
    db_path = create_db(db_name, from_chats_list)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    await bot.start()
    current_chat = None
    start_timer = time.time()

    try:
        account = await bot.get_me()
        current_datetime = datetime.now()

        cursor.execute("SELECT id, link FROM from_chats")
        from_chats = cursor.fetchall()

        for from_chat in from_chats:
            from_chat_id = from_chat[0]
            from_chat_link = from_chat[1]
            try:
                try:
                    current_chat = await join_chat(from_chat_link)

                except Exception as ex:
                    logger.info(f"Error while joining to chat {from_chat_link}, details: {ex}")
                    continue

                logger.info("Parsing type: list")
                try:
                    async for member in bot.get_chat_members(current_chat.id):
                        if (not (member.user.username or member.user.phone_number) or
                                member.user.is_bot or
                                member.user.is_deleted or
                                member.user.status == UserStatus.LONG_AGO or
                                member.status == ChatMemberStatus.OWNER or
                                member.user.id == account.id):
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
                            "phone": member.user.phone_number,
                            "photo": member.user.photo is not None,
                            "premium": member.user.is_premium,
                            "target_chat_id": from_chat_id
                        }

                        update_db(db_name, lead)

                except FloodWait as e:
                    logger.warning(f"Flood wait: {e.value} seconds")
                    await asyncio.sleep(e.value)

                except Exception as ex:
                    logger.error(f"Error parsing list, details: {ex}")
                    continue

                logger.info("Parsing type: messages")
                try:
                    async for message in bot.get_chat_history(current_chat.id):
                        date_difference = current_datetime - message.date
                        if date_difference.days >= 90:
                            break

                        if (message.sender_chat or
                                not (message.from_user.username or message.from_user.phone_number) or
                                message.from_user.is_bot or
                                message.from_user.is_deleted or
                                message.from_user.status == UserStatus.LONG_AGO or
                                message.from_user.id == account.id):
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
                            "phone": message.from_user.phone_number,
                            "photo": message.from_user.photo is not None,
                            "premium": message.from_user.is_premium,
                            "from_chat_id": from_chat_id
                        }

                        update_db(db_name, lead)

                except FloodWait as e:
                    logger.warning(f"Flood wait: {e.value} seconds")
                    await asyncio.sleep(e.value)

                except Exception as ex:
                    logger.error(f"Error parsing messages, details: {ex}")
                    continue

                cursor.execute("SELECT members FROM from_chats WHERE id = ?", (from_chat_id,))
                current_chat_members_count = cursor.fetchone()[0]
                logger.info(f"From {from_chat_link} received members: {current_chat_members_count}")

            except Exception as ex:
                logger.error(f"Error parsing members, details: {ex}")
                continue

            finally:
                try:
                    await bot.leave_chat(current_chat.id)

                except UserNotParticipant:
                    logger.warning(f"Was banned in: {from_chat_link}")

                except Exception as ex:
                    logger.error(f"Error while leaving from {from_chat_link}, details: {ex}")

                else:
                    logger.info(f"Leaved chat: {from_chat_link}")

    except Exception as ex:
        logger.error(ex)

    finally:
        conn.close()
        await bot.stop()
        total_timer = int(time.time() - start_timer)
        logger.info(f"Script worked: {format_seconds(total_timer)}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
