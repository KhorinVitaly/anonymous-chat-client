import asyncio
import gui
import datetime
import configargparse
import json
import logging
import aionursery
import contextlib
from aiofile import AIOFile
from dotenv import load_dotenv
from tkinter import messagebox
from collections import namedtuple
from async_timeout import timeout


load_dotenv()


SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE = '\n\n'


class InvalidToken(Exception):
    pass


async def create_queues():
    QueuesCollection = namedtuple('QueuesCollection', [
        'messages_queue',
        'sending_queue',
        'status_updates_queue',
        'history_queue',
        'watchdog_queue',
    ])
    return QueuesCollection(
        asyncio.Queue(),
        asyncio.Queue(),
        asyncio.Queue(),
        asyncio.Queue(),
        asyncio.Queue()
    )


@contextlib.asynccontextmanager
async def create_handy_nursery():
    try:
        async with aionursery.Nursery() as nursery:
            yield nursery
    except aionursery.MultiError as e:
        if len(e.exceptions) == 1:
            raise e.exceptions[0] from None
        raise


async def main(args):
    queues = await create_queues()
    try:
        async with create_handy_nursery() as nursery:
            nursery.start_soon(gui.draw(queues.messages_queue, queues.sending_queue, queues.status_updates_queue))
            nursery.start_soon(handle_connection(args, queues))
    except InvalidToken:
        messagebox.showerror("Не известный токен", "Проверьте токен, сервер его не узнал")
    except gui.TkAppClosed:
        pass
    except KeyboardInterrupt:
        pass


async def handle_connection(args, queues):
    pause = 0
    while True:
        queues.status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
        queues.status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
        await asyncio.sleep(pause)

        connection_for_read = await open_connection(args.host, args.read_port)
        queues.status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)

        connection_for_send = await open_connection(args.host, args.send_port)
        queues.status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
        await authorise(connection_for_send, args.token, queues)

        try:
            await create_interaction_tasks(args, queues, connection_for_read, connection_for_send)
        except asyncio.TimeoutError:
            queues.watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] 1s timeout is elapsed')
            queues.status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)
            queues.status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)
            connection_for_read.writer.close()
            connection_for_send.writer.close()
            pause = 3


async def create_interaction_tasks(args, queues, connection_for_read, connection_for_send):
    async with create_handy_nursery() as nursery:
        nursery.start_soon(read_msgs(queues, connection_for_read))
        nursery.start_soon(save_msgs(args.history, queues))
        nursery.start_soon(send_msgs(queues, connection_for_send))
        nursery.start_soon(watch_for_connection(queues))


async def open_connection(host, port):
    Connection = namedtuple('Connection', 'reader writer')
    reader, writer = await asyncio.open_connection(host, port)
    return Connection(reader, writer)


async def watch_for_connection(queues):
    while True:
        async with timeout(1):
            item = await queues.watchdog_queue.get()
            logging.debug(item)


async def read_msgs(queues, connection):
    while True:
        message = await readline(connection.reader, queues.watchdog_queue, 'New message in chat')
        if not message:
            continue
        str_datetime = datetime.datetime.now().strftime("%d %m %Y %H:%M:%S")
        message = f'[{str_datetime}] {message}'
        queues.messages_queue.put_nowait(message)
        queues.history_queue.put_nowait(message)


async def save_msgs(filepath, queues):
    while True:
        message = await queues.history_queue.get()
        async with AIOFile(filepath, 'a') as afp:
            await afp.write(message)


async def send_msgs(queues, connection):
    while True:
        message = await queues.sending_queue.get()
        await submit_message(connection.writer, queues.watchdog_queue, 'Message sent', message)


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


async def authorise(connection, token, queues):
    await readline(connection.reader, queues.watchdog_queue, 'Prompt before auth')
    await submit_message(connection.writer, queues.watchdog_queue, 'Authorization token sent', token)
    text = await readline(connection.reader, queues.watchdog_queue, 'Authorization done')
    json_data = json.loads(text)
    if not json_data:
        raise InvalidToken
    nickname = json_data['nickname']
    event = gui.NicknameReceived(nickname)
    queues.status_updates_queue.put_nowait(event)


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

