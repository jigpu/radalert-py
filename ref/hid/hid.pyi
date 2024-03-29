from typing import Any, List, Optional, Text, Union

class device:
    @classmethod
    def __init__(self) -> None: ...
    def close(self) -> None: ...
    def error(self) -> str: ...
    def get_feature_report(self, report_num: int, max_length: int) -> List[int]: ...
    def get_indexed_string(self) -> str: ...
    def get_input_report(self, report_num: int, max_length: int) -> List[int]: ...
    def get_manufacturer_string(self) -> str: ...
    def get_product_string(self) -> str: ...
    def get_serial_number_string(self) -> str: ...
    def open(self, vendor_id: Optional[int], product_id: Optional[int], serial_number: Optional[Text]) -> None: ...
    def open_path(self, path: bytes) -> None: ...
    def read(self, max_length: int, timeout_ms: Optional[int]) -> List[int]: ...
    def send_feature_report(self, buff: Any) -> int: ...
    def set_nonblocking(self, v: Union[int, bool]) -> int: ...
    def write(self, buff: Any) -> int: ...
    def __reduce__(self) -> Any: ...
    def __setstate__(self, state: Any) -> Any: ...

def enumerate(vendor_id: Optional[int], product_id: Optional[int]) -> List[dict[str,Union[Text,int]]]: ...
def hidapi_exit() -> None: ...
