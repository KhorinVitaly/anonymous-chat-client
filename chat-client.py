import asyncio
import gui
import datetime
import configargparse
from dotenv import load_dotenv
load_dotenv()


async def main(args):
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_msgs(messages_queue, args)
    )


async def read_msgs(messages_queue, args):
    reader, writer = await asyncio.open_connection(args.host, args.port)
    while True:
        data = await reader.readline()
        if not data:
            continue
        str_datetime = datetime.datetime.now().strftime("%d %m %Y %H:%M:%S")
        message = f'{str_datetime} {data.decode()}'
        messages_queue.put_nowait(message)
        await asyncio.sleep(1)


if __name__ == '__main__':
    parser = configargparse.ArgParser()
    parser.add('--host', help='Адрес сервера minechat', env_var='MINECHAT_HOST')
    parser.add('--port', help='Порт для прослушивания сообщений чата', env_var='MINECHAT_PORT_FOR_LISTENING')
    parser.add('--history', help='Путь к фалу для логирования истории чата', env_var='MINECHAT_HISTORY')
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass