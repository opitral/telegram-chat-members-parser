from telegram_chat_members_parser import Parser
import asyncio


async def main():
    parser = Parser()
    await parser.create_db()


if __name__ == "__main__":
    asyncio.run(main())
