import os
import sys
import time
from datetime import datetime, timezone
import asyncio
import logging
import configparser
import sqlite3

from pyrogram.errors import FloodWait
from telethon import TelegramClient
from telethon.tl import functions
from telethon.tl.types import UserStatusLastMonth, ChatParticipantCreator
from telethon.errors.rpcerrorlist import FloodWaitError, UserAlreadyParticipantError

from pyrogram import Client
from pyrogram.enums import UserStatus

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
api_id = int(config["Telegram"]["api_id"])
api_hash = config["Telegram"]["api_hash"]

telethon_client = TelegramClient(f"{session}_telethon", api_id, api_hash)
pyrogram_client = Client(f"{session}_pyrogram", api_id, api_hash)

logger.info(f"Session started: {session}")


def format_seconds(seconds):
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
                access_hash VARCHAR(255),
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

        for from_chat in from_chats:
            cursor.execute('''
                INSERT INTO from_chats (link) 
                VALUES (?)
            ''', (from_chat,))

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
            INSERT INTO members (
            telegram_id,
            access_hash,
            username, 
            first_name, 
            last_name, 
            phone,
            photo,
            premium,
            from_chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
                       (
                           member["telegram_id"],
                           member["access_hash"],
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


async def join_chat(chat_link):
    try:
        if chat_link.startswith("https://t.me/"):
            await telethon_client(functions.messages.ImportChatInviteRequest(chat_link.split("/")[-1].replace("+", "")))

        else:
            await telethon_client(functions.channels.JoinChannelRequest(chat_link))

        logger.info(f"Joined chat: {chat_link}")
        current_chat = await telethon_client.get_entity(chat_link)
        return current_chat

    except UserAlreadyParticipantError:
        logger.error(f"Is already a participant of the chat: {chat_link}")
        current_chat = await telethon_client.get_entity(chat_link)
        return current_chat

    except FloodWaitError as e:
        logger.warning(f"Flood wait: {e.seconds} seconds")
        await asyncio.sleep(e.seconds)
        await join_chat(chat_link)


async def main():
    db_name = sys.argv[1]
    from_chats_list = get_chats(db_name)
    db_path = create_db(db_name, from_chats_list)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    await telethon_client.start()
    await pyrogram_client.start()

    current_chat_telethon = None
    days_limit = 90
    start_timer = time.time()

    try:
        account = await pyrogram_client.get_me()
        current_datetime_pyrogram = datetime.now()
        current_datetime_telethon = datetime.now(timezone.utc)

        cursor.execute("SELECT id, link FROM from_chats")
        from_chats = cursor.fetchall()

        for from_chat in from_chats:
            from_chat_id = from_chat[0]
            from_chat_link = from_chat[1]
            try:
                try:
                    current_chat_telethon = await join_chat(from_chat_link)
                    current_chat_pyrogram = await pyrogram_client.get_chat(from_chat_link)

                except Exception as ex:
                    logger.error(f"Error while joining to group {from_chat_link}, details: {ex}")
                    continue

                logger.info("Parsing type: list")
                async for member in telethon_client.iter_participants(current_chat_telethon):
                    try:
                        if (member.bot or
                                member.deleted or
                                isinstance(member.status, (UserStatusLastMonth,)) or
                                isinstance(member.status, (ChatParticipantCreator,)) or
                                member.id == account.id):
                            continue

                        cursor.execute("SELECT * FROM members WHERE telegram_id = ?", (member.id,))
                        found_lead = cursor.fetchone()
                        if found_lead:
                            continue

                        access_hash = None
                        if not (member.username or member.phone):
                            lead_entity = await telethon_client.get_entity(member.id)
                            access_hash = lead_entity.access_hash

                        lead = {
                            "telegram_id": member.id,
                            "access_hash": access_hash,
                            "username": member.username,
                            "first_name": member.first_name,
                            "last_name": member.last_name,
                            "phone": member.phone,
                            "premium": member.premium,
                            "photo": member.photo is not None,
                            "from_chat_id": from_chat_id
                        }

                        update_db(db_name, lead)

                    except FloodWaitError as e:
                        logger.warning(f"Flood wait: {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)

                    except Exception as ex:
                        logger.error(f"Error parsing list {member}, details: {ex}")
                        continue

                logger.info("Parsing type: messages")
                logger.info("Contact with participants")
                day = 0
                async for message in telethon_client.iter_messages(current_chat_telethon):
                    try:
                        date_difference = current_datetime_telethon - message.date

                        if date_difference.days > day:
                            logger.info(f"Day: {date_difference.days}")
                            day = date_difference.days

                        if date_difference.days >= days_limit:
                            break

                    except FloodWaitError as e:
                        logger.warning(f"Flood wait: {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)

                async for message in pyrogram_client.get_chat_history(current_chat_pyrogram.id):
                    try:
                        date_difference = current_datetime_pyrogram - message.date
                        if date_difference.days >= days_limit:
                            break

                        if (message.sender_chat or
                                message.from_user.is_bot or
                                message.from_user.is_deleted or
                                message.from_user.status == UserStatus.LONG_AGO or
                                message.from_user.id == account.id):
                            continue

                        cursor.execute("SELECT * FROM members WHERE telegram_id = ?", (message.from_user.id,))
                        found_lead = cursor.fetchone()

                        if found_lead:
                            continue

                        access_hash = None
                        if not (message.from_user.username or message.from_user.phone_number):
                            lead_entity = await telethon_client.get_entity(message.from_user.id)
                            access_hash = lead_entity.access_hash

                        lead = {
                            "telegram_id": message.from_user.id,
                            "access_hash": access_hash,
                            "username": message.from_user.username,
                            "first_name": message.from_user.first_name,
                            "last_name": message.from_user.last_name,
                            "phone": message.from_user.phone_number,
                            "premium": message.from_user.is_premium,
                            "photo": message.from_user.photo is not None,
                            "from_chat_id": from_chat_id
                        }

                        update_db(db_name, lead)

                    except FloodWaitError as e:
                        logger.warning(f"Flood wait: {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)

                    except FloodWait as e:
                        logger.warning(f"Flood wait: {e.value} seconds")
                        await asyncio.sleep(e.value)

                    except Exception as ex:
                        logger.error(f"Error parsing messages {message}, details: {ex}")
                        continue

                cursor.execute("SELECT members FROM from_chats WHERE id = ?", (from_chat_id,))
                current_chat_members_count = cursor.fetchone()[0]
                logger.info(f"From {from_chat_link} received members: {current_chat_members_count}")

            except FloodWaitError as e:
                logger.warning(f"Flood wait: {e.seconds} seconds")
                await asyncio.sleep(e.seconds)

            except FloodWait as e:
                logger.warning(f"Flood wait: {e.value} seconds")
                await asyncio.sleep(e.value)

            except Exception as ex:
                logger.error(f"Error parsing members, details: {ex}")
                continue

            finally:
                try:
                    await telethon_client(functions.channels.LeaveChannelRequest(current_chat_telethon.id))

                except Exception as ex:
                    logger.error(ex)
                    logger.warning(f"Account was banned in: {from_chat_link}")

                else:
                    logger.info(f"Leaved chat: {from_chat_link}")

    except Exception as ex:
        logger.error(ex)

    finally:
        total_timer = time.time() - start_timer
        logger.info(f"Script worked: {format_seconds(total_timer)}")
        conn.close()
        await telethon_client.disconnect()
        await pyrogram_client.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
