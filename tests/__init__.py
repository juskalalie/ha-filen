import asyncio
from datetime import datetime, timedelta

async def bootstrap():
    print(datetime.now().astimezone() - timedelta(minutes=25))
    print(datetime.now())


asyncio.run(bootstrap())
