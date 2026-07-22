import re
from urllib.parse import unquote_plus


class Util:
    @staticmethod
    async def get_filename(con_disp: str) -> str:
        if con_disp is None:
            return "unknown_filename"
        fname = re.findall(r"filename\*=([^;]+)", con_disp, flags=re.IGNORECASE)
        if not fname:
            fname = re.findall(r"filename=([^;]+)", con_disp, flags=re.IGNORECASE)
        if not fname:
            return "unknown_filename"
        
        target = fname[0]
        if "utf-8''" in target.lower():
            target = re.sub(r"utf-8''", '', target, flags=re.IGNORECASE)
            target = unquote_plus(target)
        
        return target.strip().strip('"').strip("'")

    @staticmethod
    async def filter_result(result: dict,
                            filters: dict) -> bool:

        outcome = True
        for key, val in filters.items():
            if str(key) not in result or str(val).lower() not in str(result[str(key)]).lower():
                outcome = False
                break
        return outcome

    @staticmethod
    async def raise_error(status_code: int,
                          resp: str) -> None:

        raise ConnectionError(
            f'{status_code}: {resp}')

