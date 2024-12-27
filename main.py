import asyncio
import logging
import re
import sys
from os import getcwd, getenv
from os.path import join

from aiogram import Bot, Dispatcher
from aiogram.types import Message
import newrelic.agent
import sentry_sdk

from filters import PingFilter, UrlFilter, url_regex
from strategies import Provider, get_provider_by_url, registry

TOKEN = getenv("BOT_TOKEN")
DEBUG = getenv("DEBUG", False)
SENTRY_DSN = getenv("SENTRY_DSN")


dp = Dispatcher()


@dp.message(UrlFilter())
@newrelic.agent.background_task()
async def handler(message: Message) -> None:
    urls = re.findall(url_regex, message.text)

    coroutines = []
    for _url in urls:
        url = _url[0]
        provider_name = get_provider_by_url(url)
        if provider_name:
            coroutines.append(
                registry.run(
                    provider=getattr(Provider, provider_name),
                    message=message,
                    url=url,
                )
            )
    if coroutines:
        await asyncio.gather(*coroutines)


@dp.message(PingFilter())
async def ping(message: Message) -> None:
    await message.answer("pong")


async def main() -> None:
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    logger = logging.getLogger()
    logger.info(f'Launching with DEBUG mode: {"on" if DEBUG else "off"}')

    newrelic.agent.initialize(join(getcwd(), 'newrelic.ini'), environment='staging' if DEBUG else 'production')
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
        debug=DEBUG,
    )

    logger.info(f'Initialization complete.')

    asyncio.run(main())
