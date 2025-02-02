# Telegram chat members parser: первая настройка и руководство по использованию

## Первая настройка

### Подготовка
У вас должен быть установлен **Python** версии **3.10** или выше. Также убедитесь, что **pip** (Python Installs Packages) добавлен в **PATH** (переменные окружения).

Путь к рабочей директории проекта должен состоять только из **латинских** символов.

### Виртуальное окружение
#### Linux/MacOS
1. Открываем консоль и переходим в корневую папку директории с проектом (если исходники скачаны с GitHub, то этой директорией будет **telegram-chat-members-parser-main**).
2. Создаем виртуальное окружение командой `python3 -m venv venv`.
3. Активируем виртуальное окружение командой `source venv/bin/activate`.
4. Устанавливаем зависимости проекта командой `pip install -r requirements.txt`.
#### Windows
1. Открываем консоль и переходим в корневую папку директории с проектом (если исходники скачаны с GitHub, то этой директорией будет **telegram-chat-members-parser-main**).
2. Создаем виртуальное окружение командой `python -m venv venv`.
3. Активируем виртуальное окружение командой `venv\Scripts\activate`.
4. Устанавливаем зависимости проекта командой `pip install -r requirements.txt`.

### Конфигурационный файл
Создаем в корне файл `config.ini`. В рабочей директории есть пример `config.ini.example`.

Первую строку оставляем неизменной.

В строке с **session** указываем название для сессии с нашим аккаунтом.

Для получения **api_id** и **api_hash** переходим на [my.telegram.org/auth](https://my.telegram.org/auth) и регистрируем новое приложение.

В строке **history_period** указываем период (в днях) за который нужно парсить сообщения.

## Руководство по использованию
Открываем консоль, переходим в рабочую директорию и активируем виртуальное окружение в зависимости от вашей ОС.

### Создание файла с чатами для парсинга
1. В корневой папке находим директорию `src` и создаем в ней текстовый файл. Обратите внимание, что выходной файл будет иметь такое же название, как и ваш текстовый файл.
2. Открываем файл и вставляем ссылки на чаты, после чего нажимаем **Enter** и продолжаем вставлять ссылки. Если чат публичный - пишем только username (например robota_chat), если приватный - пишем полную ссылку (например https://t.me/+RGLOaTSBjK0yZGJi). Ограничений на количество чатов нет. 

В папке `src` изначально лежит файл `example.txt` с примером текстового файла.

### Запуск скрипта
Запуск парсера выполняется одной простой командой
#### Linux/MacOS
`python3 telegram_chat_members_parser_cli_client.py example`, где вместо `example` название вашего текстового файла (без расширения `.txt`).
#### Windows
`python telegram_chat_members_parser_cli_client.py example`, где вместо `example` название вашего текстового файла (без расширения `.txt`).
#### Первый запуск
Во время первого запуска вы должны создать сессию для рабочего аккаунта. Введите номер телефона, код и пройдите 2FA.
#### Выходной файл
После того, как скрипт отработает, в консоли будет сообщение об успешном завершении парсинга и путь к вашему **.db** файлу. Все выходные файлы находятся в директории `results`.
#### Примечание
Скрипт сохраняет каждых сто лидов, по этому вы можете остановить скрипт в любой момент комбинацией клавиш `control + c`. Но учтите, что при повторном запуске скрипт начнет все с начала.
#### Возможные проблемы
Если у вас возникла ошибка, откройте файл `parser.log` и найдите логи по дате. В сообщении будут указаны детали ошибки.
