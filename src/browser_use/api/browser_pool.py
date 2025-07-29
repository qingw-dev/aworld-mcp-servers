from asyncio import Semaphore

MAX_CONCURRENT_BROWSERS = 2
browser_semaphore = Semaphore(MAX_CONCURRENT_BROWSERS)