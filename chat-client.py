import asyncio
import gui
import datetime
import configargparse
from aiofile import AIOFile
from dotenv import load_dotenv
load_dotenv()


async def main(args):
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    history_queue = asyncio.Queue()
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_msgs(messages_queue, history_queue, args.host, args.port),
        save_msgs(args.history, history_queue)
    )


async def read_msgs(messages_queue, history_queue, host, port):
    reader, writer = await asyncio.open_connection(host, port)
    while True:
        data = await reader.readline()
        if not data:
            continue
        str_datetime = datetime.datetime.now().strftime("%d %m %Y %H:%M:%S")
        message = f'{str_datetime} {data.decode()}'
        messages_queue.put_nowait(message)
        history_queue.put_nowait(message)


async def save_msgs(filepath, history_queue):
    while True:
        message = await history_queue.get()
        async with AIOFile(filepath, 'a') as afp:
            await afp.write(message)


async def send_msgs(sending_queue, host, port):
    while True:
        message = await sending_queue.get()
        reader, writer = await asyncio.open_connection(host, port)


async def readline(reader):
    data = await reader.readline()
    text = data.decode()
    return text


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
