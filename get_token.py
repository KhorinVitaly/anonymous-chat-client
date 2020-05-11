import tkinter
import configargparse
import json
import asyncio
from chat_client import open_connection, submit_message, readline


async def get_token(token_label, args, username):
    connection = await open_connection(args.host, args.send_port)
    await submit_message(connection.writer)
    text = await readline(connection.reader)
    await submit_message(connection.writer)
    text = await readline(connection.reader)
    await submit_message(connection.writer, username)
    text = await readline(connection.reader)
    try:
        json_data = json.loads(text)
        token = json_data['account_hash']
        token_label['text'] = f'Ваш персональный токен: {token}'
    except ValueError:
        token_label['text'] = 'Что-то пошло не так попробуйте еще раз позже.'


def draw(args):
    root = tkinter.Tk()
    root.title('Регистрация в чате майнкрафтера')

    f_name = tkinter.Frame(root)

    name_label = tkinter.Label(f_name, text='Имя:')
    name_entry = tkinter.Entry(f_name, width=20)
    token_label = tkinter.Label(width=60, height=3, text='Введите ваше имя и нажмите зарегистрироваться')

    reg_button = tkinter.Button(text="Зарегистрироваться",
                                width=15,
                                height=3,
                                highlightbackground="lightgreen",
                                bg='lightgreen')
    reg_button['command'] = lambda: register(name_entry, token_label, args)

    f_name.pack()
    name_label.pack(side=tkinter.LEFT, padx=10, pady=10)
    name_entry.pack(side=tkinter.LEFT, padx=10, pady=10)
    reg_button.pack(padx=10, pady=10)
    token_label.pack(padx=10, pady=10)

    root.mainloop()


def register(name_entry, token_label, args):
    username = name_entry.get()
    if username:
        asyncio.run(get_token(token_label, args, username))


if __name__ == '__main__':
    parser = configargparse.ArgParser()
    parser.add('--host', help='Адрес сервера minechat', env_var='MINECHAT_HOST')
    parser.add('--send_port', help='Порт для отправки сообщений', env_var='MINECHAT_SEND_PORT')
    args = parser.parse_args()
    draw(args)
