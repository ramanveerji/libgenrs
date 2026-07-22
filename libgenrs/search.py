import re
import logging
import asyncio
import aiohttp
from .utils import Util
from pathlib import Path
from .download import LibgenDownload
from bs4 import BeautifulSoup as bsoup
from typing import Awaitable, Callable, Optional, List, Dict, Any

logg = logging.getLogger(__name__)

DEFAULT_MIRRORS = [
    'https://libgen.li',
    'https://libgen.vg',
    'https://libgen.la',
]


class Libgen:
    def __init__(self,
                 sort: str = 'def',
                 sort_mode: str = 'DESC',
                 result_limit: int = 25,
                 url: Optional[str] = None,
                 mirrors: Optional[List[str]] = None) -> None:
        """This class contains async methods to search Library Genesis mirrors and return
        a dictionary of search results using the result ID as the dictionary key.
        """

        if sort.lower() in ['def', 'id', 'author', 'title', 'publisher', 'year', 'pages', 'language', 'size', 'extension']:
            self.sort = sort.lower()
        else:
            raise ValueError(
                'sort parameter invalid. Allowed values: (def, id, author, title, publisher, year, pages, language, size, extension)'
            )
        if sort_mode.upper() in ['ASC', 'DESC']:
            self.sort_mode = sort_mode.upper()
        else:
            raise ValueError(
                'sort_mode parameter invalid. Allowed values: (ASC, DESC)'
            )
        self.result_limit = result_limit
        self.__fields = ['def', 'title', 'author', 'series', 'publisher', 'year',
                         'identifier', 'language', 'md5', 'tags', 'extension']
        
        self.mirrors = mirrors if mirrors else DEFAULT_MIRRORS.copy()
        if url:
            normalized_url = url.rstrip('/')
            if not normalized_url.startswith(('http://', 'https://')):
                normalized_url = 'https://' + normalized_url
            if normalized_url not in self.mirrors:
                self.mirrors.insert(0, normalized_url)
            self.__libgen_url = normalized_url
        else:
            self.__libgen_url = self.mirrors[0]

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        }

    async def search(self,
                     query: str,
                     search_field: str = 'def',
                     filters: dict = {},
                     return_fields: list = []) -> dict:
        """A method used to search Libgen with filters and search fields across active mirrors."""

        if not query or len(query.strip()) < 2:
            raise ValueError(f'The query "{query}" is invalid or less than 2 characters.')

        if search_field.lower() not in self.__fields:
            raise ValueError(f'search_field invalid. Allowed fields: {",".join(self.__fields)}')

        req = 'req=' + '+'.join(query.strip().split(' '))
        column = 'column=' + search_field.lower()
        sort = 'sort=' + self.sort
        sort_mode = 'sortmode=' + self.sort_mode
        res = 'res=' + str(self.result_limit)
        query_params = '&'.join([req, res, column, sort, sort_mode])

        last_exception = None
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for mirror in self.mirrors:
                base_url = mirror.rstrip('/')
                for endpoint in ['index.php', 'search.php']:
                    search_url = f'{base_url}/{endpoint}?{query_params}'
                    try:
                        ids_list, table_meta = await self.__get_ids(session, search_url)
                        if ids_list:
                            data = await self.__get_json(session, base_url, ids_list, return_fields, filters, table_meta)
                            if data:
                                self.__libgen_url = base_url
                                return data
                    except Exception as e:
                        logg.debug(f'Mirror {search_url} failed: {e}')
                        last_exception = e
                        continue

        if last_exception:
            logg.warning(f'All Libgen mirrors failed. Last error: {last_exception}')
        return {}

    async def __get_ids(self, session: aiohttp.ClientSession, url: str) -> tuple:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3.5), ssl=False) as resp:
                if resp.status != 200:
                    return [], {}
                text = await resp.text()
        except Exception:
            return [], {}

        soup = bsoup(text, 'html.parser')
        for s in soup.find_all('script'):
            s.decompose()

        table = soup.find('table', attrs={'id': 'tablelibgen'}) or soup.find('table', attrs={'rules': 'rows'})
        if not table:
            table = soup.find('table', class_=re.compile(r'table', re.I))

        if not table:
            m_req = re.search(r'[?&]req=([a-fA-F0-9]{32})', url)
            if m_req:
                return [m_req.group(1)], {}
            return [], {}

        ids = []
        table_meta = {}
        rows = table.find_all('tr')
        for tr in rows[1:]:
            tds = tr.find_all('td')
            if not tds:
                continue

            found_id = None
            for a in tr.find_all('a'):
                href = a.get('href', '')
                m_file = re.search(r'file\.php\?id=(\d+)', href)
                if m_file:
                    found_id = m_file.group(1)
                    break
                m_md5 = re.search(r'[?&]md5=([a-fA-F0-9]{32})', href)
                if m_md5:
                    found_id = m_md5.group(1)
                    break

            if not found_id:
                for a in tr.find_all('a'):
                    href = a.get('href', '')
                    m = re.search(r'[?&]id=(\d+)', href)
                    if m:
                        found_id = m.group(1)
                        break

            if not found_id and tds[0].get_text(strip=True).isdigit():
                found_id = tds[0].get_text(strip=True)

            if found_id:
                if found_id not in ids:
                    ids.append(found_id)

                if len(tds) >= 8:
                    title_a = tds[0].find('a')
                    title_text = title_a.get_text(strip=True) if title_a else tds[0].get_text(strip=True)
                    author_text = tds[1].get_text(strip=True) if len(tds) > 1 else ''
                    publisher_text = tds[2].get_text(strip=True) if len(tds) > 2 else ''
                    year_text = tds[3].get_text(strip=True) if len(tds) > 3 else ''
                    language_text = tds[4].get_text(strip=True) if len(tds) > 4 else ''
                    pages_text = tds[5].get_text(strip=True) if len(tds) > 5 else ''
                    size_text = tds[6].get_text(strip=True) if len(tds) > 6 else ''
                    ext_text = tds[7].get_text(strip=True) if len(tds) > 7 else ''

                    table_meta[str(found_id)] = {
                        'title': title_text or 'Unknown Title',
                        'author': author_text or 'Unknown Author',
                        'publisher': publisher_text,
                        'year': year_text,
                        'language': language_text,
                        'pages': pages_text,
                        'filesize': size_text,
                        'extension': ext_text or 'pdf'
                    }

        return ids, table_meta

    async def __get_json(self,
                         session: aiohttp.ClientSession,
                         base_url: str,
                         ids_list: list,
                         return_fields: list,
                         filters: dict,
                         table_meta: dict = {}) -> dict:

        ids_param = ','.join(ids_list)

        json_urls = [
            f'{base_url}/json.php?object=f&ids={ids_param}&fields=*',
            f'{base_url}/json.php?ids={ids_param}&fields=*'
        ]

        raw_data = None
        for json_url in json_urls:
            try:
                async with session.get(json_url, timeout=aiohttp.ClientTimeout(total=3.5), ssl=False) as resp:
                    if resp.status == 200:
                        raw_data = await resp.json()
                        if raw_data and not (isinstance(raw_data, dict) and 'error' in raw_data):
                            break
            except Exception as e:
                logg.debug(f'Failed json query {json_url}: {e}')

        if not raw_data and table_meta:
            raw_data = []
            for item_id in ids_list:
                if item_id in table_meta:
                    meta = table_meta[item_id]
                    raw_data.append({
                        'id': str(item_id),
                        'title': meta.get('title'),
                        'author': meta.get('author'),
                        'publisher': meta.get('publisher'),
                        'year': meta.get('year'),
                        'language': meta.get('language'),
                        'pages': meta.get('pages'),
                        'filesize': meta.get('filesize'),
                        'extension': meta.get('extension')
                    })

        if not raw_data:
            return {}

        return await self.__format_json(raw_data=raw_data,
                                        ids_list=ids_list,
                                        filters=filters,
                                        return_fields=return_fields,
                                        base_url=base_url,
                                        table_meta=table_meta)

    async def __format_json(self,
                            raw_data: Any,
                            ids_list: list,
                            filters: dict,
                            return_fields: list,
                            base_url: str,
                            table_meta: dict = {}) -> dict:

        data = {}
        normalized_data = {}
        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict) and 'id' in item:
                    normalized_data[str(item['id'])] = item
        elif isinstance(raw_data, dict):
            for item_id, item_val in raw_data.items():
                if isinstance(item_val, dict):
                    item_val['id'] = str(item_id)
                    normalized_data[str(item_id)] = item_val

        for res_id in ids_list:
            if str(res_id) in normalized_data:
                data[str(res_id)] = normalized_data[str(res_id)].copy()

        if not data and normalized_data:
            data = normalized_data.copy()

        if data:
            removed = []
            for res_id in list(data.keys()):
                item = data[res_id]
                meta = table_meta.get(str(res_id), {}) if table_meta else {}

                # Fill missing essential metadata fields using HTML table fallback
                raw_t = item.get('title', '')
                if not raw_t or raw_t == 'Unknown Title' or raw_t.lower().startswith(('z:\\', 'z:/')) or '\\scimag_' in raw_t.lower():
                    meta_t = meta.get('title', '')
                    if meta_t and meta_t != 'Unknown Title' and not meta_t.lower().startswith(('z:\\', 'z:/')) and '\\scimag_' not in meta_t.lower():
                        item['title'] = meta_t
                    else:
                        item['title'] = 'Unknown Title'

                if not item.get('author') or item.get('author') == 'Unknown Author':
                    if meta.get('author') and meta.get('author') != 'Unknown Author':
                        item['author'] = meta['author']
                    else:
                        item['author'] = 'Unknown Author'

                if not item.get('publisher') and meta.get('publisher'):
                    item['publisher'] = meta['publisher']
                if not item.get('year') and meta.get('year'):
                    item['year'] = meta['year']
                if not item.get('language') and meta.get('language'):
                    item['language'] = meta['language']
                if not item.get('pages') and meta.get('pages'):
                    item['pages'] = meta['pages']
                if not item.get('extension') and meta.get('extension'):
                    item['extension'] = meta['extension']
                if not item.get('filesize') and meta.get('filesize'):
                    item['filesize'] = meta['filesize']

                if filters:
                    if not await Util().filter_result(data[res_id], filters):
                        removed.append(res_id)
                        continue

                cover_reg = re.compile(r'^\d+\\?\/[a-z-0-9]+\..{1,4}$', re.IGNORECASE)
                if 'coverurl' in data[res_id] and data[res_id]['coverurl']:
                    if re.match(cover_reg, data[res_id]["coverurl"]):
                        data[res_id]['coverurl'] = f'{base_url}/covers/{data[res_id]["coverurl"]}'
                    elif not data[res_id]['coverurl'].startswith('http'):
                        data[res_id]['coverurl'] = f'{base_url}/covers/{data[res_id]["coverurl"]}'
                else:
                    data[res_id]['coverurl'] = None

                if not return_fields or 'mirrors' in return_fields:
                    md5 = data[res_id].get('md5', '')
                    sha1 = data[res_id].get('sha1', '')
                    size = data[res_id].get('filesize', '0')
                    edonkey = data[res_id].get('edonkey', '')
                    aich = data[res_id].get('aich', '')
                    tth = data[res_id].get('tth', '')
                    extension = data[res_id].get('extension', '')

                    if return_fields:
                        for fld in ['md5', 'sha1', 'filesize', 'edonkey', 'aich', 'tth', 'extension']:
                            if fld not in return_fields and fld in data[res_id]:
                                data[res_id].pop(fld, None)

                    tor_number = str(res_id)[:-3] + '000' if res_id.isdigit() and int(res_id) >= 1000 else '000'
                    
                    data[res_id]['mirrors'] = {
                        'main': f'{base_url}/ads.php?md5={md5}',
                        'libgen.lc': f'https://libgen.li/ads.php?md5={md5}',
                        'library.lol': f'https://library.lol/main/{md5}',
                        'z-library': f'https://annas-archive.org/md5/{md5}',
                        'libgen.pw': f'{base_url}/file.php?id={res_id}',
                        'torrent': f'{base_url}/book/index.php?md5={md5}&oftorrent=',
                        'torrent_1k': f'{base_url}/repository_torrent/r_{tor_number}.torrent',
                        'gnutella': f'magnet:?xt=urn:sha1:{sha1}&xl={size}&dn={md5}.{extension}',
                        'ed2k': f'ed2k://|file|{md5.upper()}.{extension}|{size}|{edonkey}|h={aich}|/',
                        'dc++': f'magnet:?xt=urn:tree:tiger:{tth}&xl={size}&dn={md5}.{extension}'
                    }

                data[res_id].pop('torrent', None)
                data[res_id].pop('locator', None)
                data[res_id].pop('id', None)

            for res_id in removed:
                data.pop(res_id, None)

        logg.info(f'Finished processing {len(data)} results.')
        return data

    @staticmethod
    async def download(url: str,
                       dest_folder: Path = None,
                       progress: Optional[Callable[..., Awaitable[None]]] = None,
                       progress_args: list = []) -> Path:
        return await LibgenDownload().download(url,
                                               dest_folder,
                                               progress,
                                               progress_args)
