import logging
from .search import Libgen
from .download import LibgenDownload

__version__ = '0.3.6'
__all__ = ['Libgen', 'LibgenDownload']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger(__name__)
