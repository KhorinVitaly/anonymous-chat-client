import asyncio
import gui
import datetime
import configargparse
import json
import logging
from aiofile import AIOFile
from dotenv import load_dotenv
from tkinter import messagebox
from collections import namedtuple
from async_timeout import timeout


load_dotenv()


SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE = '\n\n'


class InvalidToken(Exception):
    pass


async def main(args):
    try:
        messages_queue = asyncio.Queue()
        sending_queue = asyncio.Queue()
        status_updates_queue = asyncio.Queue()
        await asyncio.gather(
            gui.draw(messages_queue, sending_queue, status_updates_queue),
            handle_connection(args, messages_queue, sending_queue, status_updates_queue)
        )
    except gui.TkAppClosed:
        pass
    except InvalidToken:
        messagebox.showerror("Не известный токен", "Проверьте токен, сервер его не узнал")
    except KeyboardInterrupt:
        pass


async def handle_connection(args, messages_queue, sending_queue, status_updates_queue):
    history_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    connection_for_read = await open_connection(args.host, args.read_port)
    status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)

    connection_for_send = await open_connection(args.host, args.send_port)
    await authorise(connection_for_send, args.token, status_updates_queue, watchdog_queue)
    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)

    await asyncio.gather(
        read_msgs(messages_queue, history_queue, watchdog_queue, connection_for_read.reader),
        save_msgs(args.history, history_queue),
        send_msgs(sending_queue, watchdog_queue, connection_for_send.writer),
        watch_for_connection(watchdog_queue),
    )


async def open_connection(host, port):
    Connection = namedtuple('Connection', 'reader writer')
    reader, writer = await asyncio.open_connection(host, port)
    return Connection(reader, writer)


async def watch_for_connection(watchdog_queue):
    while True:
        async with timeout(1) as cm:
            item = await watchdog_queue.get()
            logging.debug(item)
        if cm.expired:
            watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] 1s timeout is elapsed')


async def read_msgs(messages_queue, history_queue, watchdog_queue, reader):
    while True:
        message = await readline(reader, watchdog_queue, 'New message in chat')
        if not message:
            continue
        str_datetime = datetime.datetime.now().strftime("%d %m %Y %H:%M:%S")
        message = f'[{str_datetime}] {message}'
        messages_queue.put_nowait(message)
        history_queue.put_nowait(message)


async def save_msgs(filepath, history_queue):
    while True:
        message = await history_queue.get()
        async with AIOFile(filepath, 'a') as afp:
            await afp.write(message)


async def send_msgs(sending_queue, watchdog_queue, writer):
    while True:
        message = await sending_queue.get()
        await submit_message(writer, watchdog_queue, 'Message sent', message)


async def submit_message(writer,  watchdog_queue, description, text=''):
    text = await sanitize(text)
    text += SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE
    data = text.encode('utf-8')
    writer.write(data)
    await writer.drain()
    watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] Connection is alive. {description}')


async def sanitize(text):
    return text.replace('\n', '\\n')


async def readline(reader, watchdog_queue, description):
    data = await reader.readline()
    if not data:
        return
    text = data.decode()
    watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] Connection is alive. {description}')
    return text


async def authorise(connection, token, status_updates_queue, watchdog_queue):
    await readline(connection.reader, watchdog_queue, 'Prompt before auth')
    await submit_message(connection.writer, watchdog_queue, 'Authorization token sent', token)
    text = await readline(connection.reader, watchdog_queue, 'Authorization done')
    json_data = json.loads(text)
    if not json_data:
        raise InvalidToken
    nickname = json_data['nickname']
    event = gui.NicknameReceived(nickname)
    status_updates_queue.put_nowait(event)


if __name__ == '__main__':
    parser = configargparse.ArgParser()
    parser.add('--host', help='Адрес сервера minechat', env_var='MINECHAT_HOST')
    parser.add('--read_port', help='Порт для получения сообщений чата', env_var='MINECHAT_READ_PORT')
    parser.add('--send_port', help='Порт для отправки сообщений чата', env_var='MINECHAT_SEND_PORT')
    parser.add('--history', help='Путь к фалу для логирования истории чата', env_var='MINECHAT_HISTORY')
    parser.add('--token', help='Персоональный hash токен для авторизации', env_var='TOKEN')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(args))

