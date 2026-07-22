import re
import time
import aiohttp
import aiofiles
import logging
from .utils import Util
from pathlib import Path
from tldextract import extract
from bs4 import BeautifulSoup as bsoup
from typing import Awaitable, Callable, Optional, List
from urllib.parse import urljoin

logg = logging.getLogger(__name__)


class LibgenDownload:
    def __init__(self) -> None:
        self.dest_folder = Path.cwd()
        self.mirrors = [
            'libgen.li',
            'libgen.lc',
            'libgen.gs',
            'libgen.is',
            'libgen.rs',
            'libgen.st',
            'library.lol',
            'books.ms',
            'b-ok.cc',
            'annas-archive.org',
            'annas-archive.gl'
        ]
        self.regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    async def download(self,
                       url: str,
                       dest_folder: Path = None,
                       progress: Optional[Callable[..., Awaitable[None]]] = None,
                       progress_args: list = []) -> Path:

        if not re.match(self.regex, url):
            raise ValueError(f'Invalid URL: {url}')

        ext_info = extract(url)
        domain_name = f'{ext_info.domain}.{ext_info.suffix}'.lower()
        if domain_name not in self.mirrors and ext_info.domain.lower() not in [m.split('.')[0] for m in self.mirrors]:
            logg.warning(f'Domain {domain_name} not in standard mirrors list, proceeding anyway.')

        if not dest_folder:
            dest_folder = self.dest_folder
        else:
            dest_folder = Path(dest_folder)
        
        dest_folder.mkdir(parents=True, exist_ok=True)

        direct_links = await self.get_directlink(url)
        if not direct_links:
            # Try using url directly as fallback
            direct_links = [url]

        for link in direct_links:
            file = await self.__download(link,
                                         dest_folder,
                                         progress,
                                         progress_args)
            if file and file.exists():
                return file
        
        logg.error('Could not download the book from the given url.')
        return None

    @staticmethod
    async def __download(url: str,
                         dest_folder: Path,
                         progress: Optional[Callable[..., Awaitable[None]]],
                         progress_args: list) -> Path:

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36'
            }
            async with aiohttp.ClientSession(headers=headers) as dl_ses:
                async with dl_ses.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status != 200:
                        logg.error(f'Download HTTP status {resp.status} for {url}')
                        return None

                    content_length = resp.headers.get('Content-Length')
                    total_size = int(content_length) if content_length and content_length.isdigit() else 'Unknown size'
                    
                    file_name = await Util().get_filename(resp.headers.get('Content-Disposition'))
                    if file_name == "unknown_filename":
                        # Attempt to extract filename from URL
                        url_filename = url.split('/')[-1].split('?')[0]
                        if url_filename and '.' in url_filename:
                            file_name = url_filename
                        else:
                            file_name = "downloaded_book"

                    temp_file = dest_folder / file_name

                    async with aiofiles.open(temp_file, mode="wb") as dl_file:
                        current = 0
                        logg.info(f'Starting download: {file_name}')
                        st_time = time.time()
                        async for chunk, _ in resp.content.iter_chunks():
                            await dl_file.write(chunk)
                            current += len(chunk)
                            cr_time = time.time()
                            if cr_time - st_time > 1:
                                if progress:
                                    try:
                                        await progress(current, total_size, *progress_args)
                                    except Exception as pe:
                                        logg.warning(f'Progress callback error: {pe}')
                                logg.debug(f'Downloading: {current} of {total_size} Done.')
                                st_time = cr_time

                        if progress:
                            try:
                                await progress(current, total_size, *progress_args)
                            except Exception:
                                pass

                    return temp_file
        except Exception as e:
            logg.exception(f'Error downloading from {url}: {e}')
            return None

    async def get_directlink(self, url: str) -> List[str]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        }
        direct_links = []
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return [url]
                    text = await resp.text()

            soup = bsoup(text, 'html.parser')
            for s in soup.find_all('script'):
                s.decompose()

            # Check get.php or download links for libgen.li / libgen.lc / libgen.gs
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if 'get.php' in href or 'download' in href.lower() or 'cloudflare' in href.lower():
                    full_link = urljoin(url, href)
                    if full_link not in direct_links:
                        direct_links.append(full_link)

            # Check library.lol format
            if not direct_links:
                info_div = soup.find('div', attrs={'id': 'info'}) or soup.find('div', attrs={'id': 'download'})
                if info_div:
                    for a in info_div.find_all('a'):
                        href = a.get('href', '')
                        if href.startswith('http'):
                            direct_links.append(href)

            # General fallback for any primary download <a> links
            if not direct_links:
                for a in soup.find_all('a'):
                    href = a.get('href', '')
                    if href.startswith('http') and any(ext in href.lower() for ext in ['.pdf', '.epub', '.mobi', '.djvu', 'get.php']):
                        direct_links.append(href)

        except Exception as e:
            logg.warning(f'Failed to extract direct links from {url}: {e}')

        return direct_links if direct_links else [url]
