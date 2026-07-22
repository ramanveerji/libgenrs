# libgenrs

Asynchronous Python library for Library Genesis (Libgen) to search and download books.

[![PyPI version](https://badge.fury.io/py/libgenrs.svg)](https://pypi.org/project/libgenrs)
[![Build Python Package](https://github.com/ramanveerji/libgenrs/actions/workflows/python-publish.yml/badge.svg)](https://github.com/ramanveerji/libgenrs/actions/workflows/python-publish.yml)

## Features

- **True Asynchronous Architecture**: Uses `aiohttp` for non-blocking search and download.
- **Automatic Mirror Failover**: Automatically cycles through working active Libgen mirrors (`libgen.li`, `libgen.lc`, `libgen.is`, `libgen.rs`, `libgen.st`) if a domain is blocked or offline.
- **Configurable Domain Support**: Pass custom mirror domains directly on initialization.
- **Multi-Schema HTML & JSON Support**: Supports both standard Libgen and Libgen.lc table & JSON layouts.

## Installing libgenrs

```bash
pip install libgenrs
```

## Importing libgenrs

```python
from libgenrs import Libgen
```

## Creating libgenrs object

```python
lg = Libgen()
```

or with custom options:

```python
lg = Libgen(url='https://libgen.li', sort='year', sort_mode='ASC', result_limit=50)
```

### Options:

- **url**: Set a custom primary Libgen domain (e.g. `'https://libgen.li'`). If omitted, automatically attempts active mirrors with automatic failover.
- **sort**: Method to sort results (`'def'`, `'id'`, `'author'`, `'title'`, `'publisher'`, `'year'`, `'pages'`, `'language'`, `'size'`, `'extension'`). Defaults to `'def'`.
- **sort_mode**: Sort order (`'ASC'`, `'DESC'`). Defaults to `'DESC'`.
- **result_limit**: Number of results (25, 50, 100). Defaults to 25.

## Searching for a book

```python
import asyncio
from libgenrs import Libgen

async def main():
    lg = Libgen()
    result = await lg.search('japan history')
    for item_id, item_info in result.items():
        print(f"ID: {item_id}")
        print(f"Title: {item_info.get('title')}")
        print(f"MD5: {item_info.get('md5')}")
        print(f"Main Download Link: {item_info.get('mirrors', {}).get('main')}")
        print('-' * 40)

asyncio.run(main())
```

## Downloading a book

```python
import asyncio
from pathlib import Path
from libgenrs import Libgen

async def progress(current, total, title):
    print(f"Downloading {title}: {current} / {total} bytes")

async def main():
    lg = Libgen()
    result = await lg.search('japan history')
    if result:
        first_id = list(result.keys())[0]
        download_url = result[first_id]['mirrors']['main']
        title = result[first_id].get('title', 'book')
        
        saved_file = await lg.download(download_url,
                                       dest_folder=Path('Downloads'),
                                       progress=progress,
                                       progress_args=[title])
        print(f"Downloaded to: {saved_file}")

asyncio.run(main())
```
