import asyncio
import logging
from random import randint
import re
import sys
from os import getcwd, getenv, remove
from os.path import join, exists

from aiogram import Bot, Dispatcher
from aiogram.enums import ContentType
from aiogram.types import Message, URLInputFile
from aiogram.filters.command import Command
import newrelic.agent
import sentry_sdk

from filters import UrlFilter, url_regex, VasyaFilter, VasyaBurntFilter, JoinedFilter
from strategies import Provider, get_provider_by_url, registry

TOKEN = getenv("BOT_TOKEN")
DEBUG = getenv("DEBUG", False)
SENTRY_DSN = getenv("SENTRY_DSN")


dp = Dispatcher()


def is_vasya_burnt() -> bool:
    return exists('.vasya_burnt')


def set_vasya_burnt(is_burnt) -> None:
    if is_burnt:
        with open('.vasya_burnt', 'w') as f:
            f.write(' ')
    else:
        try:
            remove('.vasya_burnt')
        except FileNotFoundError:
            pass


@dp.message(UrlFilter())
@newrelic.agent.background_task()
async def handler(message: Message) -> None:
    urls = re.findall(url_regex, message.text)

    if message.reply_to_message:
        message = message.reply_to_message

    coroutines = []
    for _url in urls:
        url = _url[0]
        if provider_name := get_provider_by_url(url):
            coroutines.append(
                registry.run(
                    provider=getattr(Provider, provider_name),
                    message=message,
                    url=url,
                )
            )
    if not coroutines:
        return
    try:
        # 2 minutes should be enough even for IG on raspberry
        async with asyncio.timeout(120):
            await asyncio.gather(*coroutines)
    except TimeoutError:
        pass



@dp.message(VasyaFilter())
async def vasya_handler(message: Message) -> None:
    await message.answer_animation(
        'CgACAgIAAxkBAAIBu2kToK0i0ZgH4INiOWSh9j4_QyN7AAK1fQACuuuhSN0amQABRYjNkDYE',
        reply_to_message_id=message.message_id
    )

    if randint(0, 1):
        await asyncio.sleep(randint(1, 5) * 60 * 60)
        if not is_vasya_burnt():
            await message.answer('.', reply_to_message_id=message.message_id)


@dp.message(VasyaBurntFilter())
async def vasya_burnt_handler(message: Message) -> None:
    set_vasya_burnt(not is_vasya_burnt())


@dp.message(Command('ping'))
async def ping(message: Message) -> None:
    await message.answer('pong', reply_to_message_id=message.message_id)


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


@dp.message(JoinedFilter())
async def joined(message: Message) -> None:
    await message.answer_video(
        URLInputFile('https://media1.tenor.com/m/x8v1oNUOmg4AAAAC/rickroll-roll.gif'),
        reply_to_message_id=message.message_id
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info(f'Launching with DEBUG mode: {"on" if DEBUG else "off"}')

    if not DEBUG:
        newrelic.agent.initialize(join(getcwd(), 'newrelic.ini'), environment='production')
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for tracing.
            traces_sample_rate=1.0,
            _experiments={
                # Set continuous_profiling_auto_start to True
                # to automatically start the profiler when
                # possible.
                "continuous_profiling_auto_start": True,
            },
        )

    logger.info(f'Initialization complete.')

    asyncio.run(main())
