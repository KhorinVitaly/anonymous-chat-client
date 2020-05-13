# anonymous-chat-client

Пример реализации взаимойствения с чатом на TCP сокетах с помощью Python и asyncio.

Содержит скрипт chat_client.py для запуска чата в графическом инерфейсе и скрипт get_token.py
для регистрации в чате и получения персонального токена.

## Как установить

Для работы скриптов нужен Python версии не ниже 3.7. Для установки необходимых зависимостей, в терминале
наберите команду:

```bash
pip install -r requirements.txt
```

## Как запустить

Для запуска чата в графическом интерфейсе, в терминале наберите команду:

```bash
python chat_client.py
```

Для запуска интерфейса регистрации, в терминале наберите команду:

```bash
python get_token.py
```

### Параметры и переменные окружения

При запуске скрипта chat_client.py вы можете указать следующие необязательные параметры:

```bash
--host - адрес сервера чата
--read_port - порт для получения истории сообщений
--send_port - порт для отправки сообщений
--history - путь к файлу для логирования истории чата
--token - персональный токен необходимый для авторизации уже существующего пользователя
```

```bash
python listen_minechat.py --host minechat.dvmn.org --read_port 5000 --history ./chat_hystory.log
```

Альтернативой является установка переменных окружения:

```env
MINECHAT_HOST
MINECHAT_READ_PORT
MINECHAT_SEND_PORT
MINECHAT_HISTORY
MINECHAT_TOKEN
```

```bash
export MINECHAT_HOST=minechat.dvmn.org && export MINECHAT_SEND_PORT=5000
```

Также при запуске get_token.py доступны следующие параметры:

```bash
--host - адрес сервера чата
--send_port - порт для отправки сообщений
```

```bash
python get_token.py --host minechat.dvmn.org --send_port 5050
```

Альтернативой также является установка соответствующих переменных окружения:

```env
MINECHAT_HOST
MINECHAT_SEND_PORT
```

```bash
export MINECHAT_HOST=minechat.dvmn.org && export MINECHAT_SEND_PORT=5050
```

Также поддерживается использование .env файлов для описания переменных окружения:

```env
MINECHAT_HOST=minechat.dvmn.org
MINECHAT_READ_PORT=5000
MINECHAT_SEND_PORT=5050
MINECHAT_HISTORY=./chat.log
MINECHAT_TOKEN=5fvg.........
```

## Цели проекта

Код написан в учебных целях — это урок в курсе по aсинхронному программированию на Python на сайте [Devman](https://dvmn.org).
