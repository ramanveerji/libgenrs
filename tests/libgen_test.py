from libgenrs import Libgen, LibgenDownload
from pathlib import Path
import pytest


class Testclass:
    """Testing of Libgen object, searching, result types, and download of the books."""
    @staticmethod
    def test_Libgen():
        # create a Libgen object with custom settings
        lg = Libgen(sort="title", sort_mode="ASC", result_limit=50, url="https://libgen.li")
        assert isinstance(lg, Libgen)
        assert lg.result_limit == 50

    @staticmethod
    @pytest.mark.asyncio
    async def test_search():
        lg = Libgen()
        result = await lg.search('python')
        assert isinstance(result, dict)
        assert len(result) > 0

    @staticmethod
    @pytest.mark.asyncio
    async def test_result():
        lg = Libgen()
        result = await lg.search('python')
        assert isinstance(result, dict)
        ids = list(result.keys())
        assert len(ids) > 0
        first_item = result[ids[0]]
        assert isinstance(first_item, dict)
        assert 'title' in first_item or 'md5' in first_item
        assert 'mirrors' in first_item

    @staticmethod
    @pytest.mark.asyncio
    async def test_download():
        lg = Libgen()
        result = await lg.search('python')
        ids = list(result.keys())
        assert len(ids) > 0

        async def progress(current, total, test_arg, test2_arg):
            assert isinstance(current, int)
            assert isinstance(total, (int, str))
            assert isinstance(test_arg, Libgen) and test_arg.test == 'Test string'
            assert isinstance(test2_arg, int) and test2_arg == 123456

        lg.test = 'Test string'
        download_url = result[ids[0]]['mirrors']['main']
        dest_dir = Path("download_test")

        file = await lg.download(download_url,
                                 dest_folder=dest_dir,
                                 progress=progress,
                                 progress_args=[lg, 123456])
        
        assert file is not None
        assert file.exists()
        assert file.is_file()
        
        # Cleanup downloaded test file
        if file.exists():
            file.unlink()
        if dest_dir.exists() and not any(dest_dir.iterdir()):
            dest_dir.rmdir()
