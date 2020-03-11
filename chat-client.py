import asyncio
import gui
import datetime
import configargparse
import json
from aiofile import AIOFile
from dotenv import load_dotenv
from tkinter import messagebox


load_dotenv()


SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE = '\n\n'


class InvalidToken(Exception):
    pass


async def main(args):
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    history_queue = asyncio.Queue()
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_msgs(messages_queue, history_queue, args.host, args.read_port),
        save_msgs(args.history, history_queue),
        send_msgs(sending_queue, args.host, args.send_port, args.token, status_updates_queue),
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


async def send_msgs(sending_queue, host, port, token, status_updates_queue):
    reader, writer = await asyncio.open_connection(host, port)
    await readline(reader)
    await authorise(reader, writer, token, status_updates_queue)
    while True:
        message = await sending_queue.get()
        await submit_message(writer, message)


async def submit_message(writer, text=''):
    text = await sanitize(text)
    text += SPECIAL_SYMBOLS_FOR_MARKING_END_OF_MESSAGE
    data = text.encode('utf-8')
    writer.write(data)
    await writer.drain()


async def sanitize(text):
    return text.replace('\n', '\\n')


async def readline(reader):
    data = await reader.readline()
    text = data.decode()
    return text


async def authorise(reader, writer, token, status_updates_queue):
    await submit_message(writer, token)
    text = await readline(reader)
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
    try:
        asyncio.run(main(args))
    except gui.TkAppClosed:
        pass
    except InvalidToken:
        messagebox.showerror("Не известный токен", "Проверьте токен, сервер его не узнал")
    except KeyboardInterrupt:
        pass
