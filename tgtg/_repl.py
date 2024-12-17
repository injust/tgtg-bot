from __future__ import annotations

import atexit
from http.cookiejar import MozillaCookieJar
from json import JSONDecodeError
from pathlib import Path

from loguru import logger

from .client import TgtgClient
from .models import Credentials

COOKIES_PATH = (Path.cwd() / "cookies.txt").resolve()
CREDENTIALS_PATH = (Path.cwd() / "credentials.json").resolve()


async def make_client(email: str = "") -> TgtgClient:
    cookies = MozillaCookieJar(COOKIES_PATH)

    if email:
        client = TgtgClient.from_email(email, cookies)
    else:
        try:
            credentials = Credentials.load(CREDENTIALS_PATH)
        except (FileNotFoundError, JSONDecodeError, TypeError) as e:
            logger.debug(e)
            logger.error("Could not load credentials from {!r}", str(CREDENTIALS_PATH))
            return await make_client(input("Email: "))
        else:
            client = TgtgClient.from_credentials(credentials, cookies)

    atexit.register(client.cookies.save, str(COOKIES_PATH))
    # `Credentials` instance is replaced on refresh
    atexit.register(lambda: client.credentials.save(CREDENTIALS_PATH))
    return await client.__aenter__()
