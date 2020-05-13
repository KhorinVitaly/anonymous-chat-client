import asyncio
import gui
import datetime
import configargparse
import json
import logging
import aionursery
import contextlib
import anyio
from aiofile import AIOFile
from dotenv import load_dotenv
from tkinter import messagebox
from collections import namedtuple
from async_timeout import timeout
from socket import gaierror


SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE = '\n\n'


class InvalidToken(Exception):
    pass


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
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    try:
        async with create_handy_nursery() as nursery:
            nursery.start_soon(gui.draw(messages_queue, sending_queue, status_updates_queue))
            nursery.start_soon(handle_connection(args, messages_queue, sending_queue, status_updates_queue))
    except InvalidToken:
        messagebox.showerror("Не известный токен", "Проверьте токен, сервер его не узнал")
    except gui.TkAppClosed:
        pass
    except KeyboardInterrupt:
        pass


async def handle_connection(args, messages_queue, sending_queue, status_updates_queue):
    while True:
        history_queue = asyncio.Queue()
        watchdog_queue = asyncio.Queue()
        state_enum = gui.SendingConnectionStateChanged
        try:
            async with open_connection(args.host, args.send_port, status_updates_queue, state_enum) as connection:
                await authorise(connection, args.token, watchdog_queue, status_updates_queue)
                async with anyio.create_task_group() as tg:
                    await tg.spawn(read_msgs, args, watchdog_queue, messages_queue, history_queue, status_updates_queue)
                    await tg.spawn(save_msgs, args.history, history_queue)
                    await tg.spawn(send_msgs, connection, sending_queue, watchdog_queue)
                    await tg.spawn(watch_for_connection, watchdog_queue)
                    await tg.spawn(keep_in_touch, connection, watchdog_queue)
        except ConnectionError:
            pass


@contextlib.asynccontextmanager
async def open_connection(host, port, status_updates_queue=None, state_enum=None):
    is_opened = False
    if status_updates_queue and state_enum:
        status_updates_queue.put_nowait(state_enum.INITIATED)
    Connection = namedtuple('Connection', 'reader writer')
    try:
        reader, writer = await asyncio.open_connection(host, port)
        if status_updates_queue and state_enum:
            status_updates_queue.put_nowait(state_enum.ESTABLISHED)
        is_opened = True
        yield Connection(reader, writer)
    except gaierror:
        raise ConnectionError
    finally:
        if is_opened:
            writer.close()
        if status_updates_queue and state_enum:
            status_updates_queue.put_nowait(state_enum.CLOSED)


async def watch_for_connection(watchdog_queue):
    pause = 1
    while True:
        try:
            async with timeout(pause) as cm:
                item = await watchdog_queue.get()
                logging.debug(item)
        except asyncio.TimeoutError:
            if cm.expired:
                logging.debug(f'[{datetime.datetime.now().timestamp()}] {pause}s timeout is elapsed')
                raise ConnectionError


async def keep_in_touch(connection, watchdog_queue):
    pause = 0.5
    while True:
        await submit_message(connection.writer, '', watchdog_queue, 'ping')
        answer = await readline(connection.reader, watchdog_queue, 'pong')
        if not answer:
            break
        await anyio.sleep(pause)


async def read_msgs(args, watchdog_queue, messages_queue, history_queue, status_updates_queue):
    state_enum = gui.ReadConnectionStateChanged
    async with open_connection(args.host, args.read_port, status_updates_queue, state_enum) as connection:
        while True:
            message = await readline(connection.reader, watchdog_queue, 'New message in chat')
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


async def send_msgs(connection, sending_queue, watchdog_queue):
    while True:
        message = await sending_queue.get()
        await submit_message(connection.writer, message, watchdog_queue, 'Message sent')


async def submit_message(writer, text='', watchdog_queue=None, description=''):
    text = await sanitize(text)
    text += SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE
    data = text.encode('utf-8')
    writer.write(data)
    await writer.drain()
    if watchdog_queue:
        watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] Connection is alive. {description}')


async def sanitize(text):
    return text.replace('\n', '\\n')


async def readline(reader, watchdog_queue=None, description=''):
    data = await reader.readline()
    if not data:
        return
    text = data.decode()
    if watchdog_queue:
        watchdog_queue.put_nowait(f'[{datetime.datetime.now().timestamp()}] Connection is alive. {description}')
    return text


async def authorise(connection, token, watchdog_queue, status_updates_queue):
    await readline(connection.reader, watchdog_queue, 'Prompt before auth')
    await submit_message(connection.writer, token, watchdog_queue, 'Authorization token sent')
    text = await readline(connection.reader, watchdog_queue, 'Authorization done')
    json_data = json.loads(text)
    if not json_data:
        raise InvalidToken
    nickname = json_data['nickname']
    event = gui.NicknameReceived(nickname)
    status_updates_queue.put_nowait(event)


if __name__ == '__main__':
    load_dotenv()
    parser = configargparse.ArgParser()
    parser.add('--host', help='Адрес сервера minechat', env_var='MINECHAT_HOST')
    parser.add('--read_port', help='Порт для получения сообщений чата', env_var='MINECHAT_READ_PORT')
    parser.add('--send_port', help='Порт для отправки сообщений чата', env_var='MINECHAT_SEND_PORT')
    parser.add('--history', help='Путь к фалу для логирования истории чата', env_var='MINECHAT_HISTORY')
    parser.add('--token', help='Персональный hash токен для авторизации', env_var='MINECHAT_TOKEN')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    if args.host and args.send_port and args.read_port:
        asyncio.run(main(args))
    else:
        messagebox.showerror("Ошибка", "Не заданы параметры подлючения")
