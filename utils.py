"""实用工具"""

from datetime import date
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from re import findall, sub, match
from collections import ChainMap
from urllib.parse import quote, urlparse
from time import time
from io import BytesIO

from requests import get, Session, Response
from PIL import Image
from bs4 import BeautifulSoup
from streamlit.elements.lib.mutable_status_container import StatusContainer

# 请求超时，单位：秒
REQUEST_TIMEOUT = 10

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Dnt": "1",
    "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Gpc": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
}


class StandardType(Enum):
    """标准类型"""

    GB = "GB"
    GBT = "GB/T"
    GBZ = "GB/Z"


@dataclass
class StandardNumber:
    """
    标准号的数据结构

    原始标准号：
    GB 123456.1-2000
     |    |   |   |
     |    |   |   ┕—— year
     |    |   ┕—— part_number
     |    ┕—— number
     ┕—— type
    """

    # GB、GBT、GBZ
    type: StandardType
    # 标准编号
    number: int
    # 标准部分编号
    part_number: Optional[int]
    # 标准发布年份
    year: Optional[int]

    def __post_init__(self):
        if not self.is_valid_year(self.year) or not isinstance(self.type, StandardType):
            raise ValueError(
                f"year 参数应为 1949-{date.today().year}之间的年份，且 type 参数需为 StandardType 类型之一。"
            )

    @staticmethod
    def is_valid_year(year: Optional[int]):
        """是否为有效的发布年份"""
        return year is None or (
            isinstance(year, int) and 1949 <= year <= date.today().year
        )

    def __str__(self) -> str:
        return (
            f"{self.type.value} {self.number}"
            + (f".{self.part_number}" if self.part_number else "")
            + (f"-{self.year}" if self.year else "")
        )


@dataclass
class StandardIdentifier:
    """
    标准标识符的数据结构
    为了下载，只有 samr_openstd_id 是必须的。
    为了展示，需要 number 和 name。
    由 samr_std_id 可以很容易的获取 samr_openstd_id 和 number。
    由 samr_openstd_id 也可以通过如下方法获取 samr_std_id：
    ```python
    get(
        f"https://openstd.samr.gov.cn/bzgk/gb/review?hcno={samr_openstd_id}",
        allow_redirects=False,
    ).headers["Location"]
    ```
    """

    # https://std.samr.gov.cn/gb/search/gbDetailed?id=
    samr_std_id: Optional[str]
    # https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=
    # http://c.gb688.cn/bzgk/gb/showGb?type=online&hcno=
    # http://c.gb688.cn/bzgk/gb/showGb?type=download&hcno=
    samr_openstd_id: str

    number: StandardNumber
    name: str

    def __post_init__(self):
        self.name = sub(r"\s+", " ", self.name)


def log_request(response: Response):
    """Log a request"""
    color_code = 37
    if 200 <= response.status_code < 300:
        color_code = 32
    elif 300 <= response.status_code < 400:
        color_code = 34
    elif 400 <= response.status_code < 600:
        color_code = 31

    print(
        f"\x1B[{color_code}m{response.status_code}\x1B[0m \x1B[33m{response.url}\x1B[0m"
    )


def parse_standard_number(standard_number: str) -> StandardNumber:
    """解析标准号"""
    standard_type, number, part_number, year = findall(
        r"(?P<type>GB/?[TZ]?)? ?(?P<number>\d+)(?:\.(?P<part_number>\d+))?(?:-(?P<year>\d{4}))?",
        standard_number,
    )[0]

    return StandardNumber(
        type=StandardType(standard_type),
        number=int(number),
        part_number=int(part_number) if part_number else None,
        year=int(year) if year else None,
    )


def get_identifier_by_samr_std_id(samr_std_id: str) -> StandardIdentifier:
    """根据 samr_std_id 获取 identifier"""

    response = get(
        f"https://std.samr.gov.cn/gb/search/gbDetailed?id={samr_std_id}",
        headers=dict(ChainMap({"Host": "std.samr.gov.cn"}, HEADERS)),
        timeout=REQUEST_TIMEOUT,
    )
    log_request(response)

    samr_openstd_id = findall(
        r"window\.open\('http://openstd\.samr\.gov\.cn/bzgk/gb/newGbInfo\?hcno=(\S+)','_blank'\);",
        response.text,
    )[0]
    standard_number = findall(
        r'<dt class="basicInfo-item name">标准号</dt>\s*'
        '<dd class="basicInfo-item value">(.+)</dd>',
        response.text,
    )[0]
    name = findall(r"<h4 style=\".+\">(.+)</h4>", response.text)[0]

    return StandardIdentifier(
        samr_std_id=samr_std_id,
        samr_openstd_id=samr_openstd_id,
        number=parse_standard_number(standard_number),
        name=name,
    )


def get_identifier_by_samr_openstd_id(samr_openstd_id: str) -> StandardIdentifier:
    """根据 samr_openstd_id 获取 identifier"""

    response = get(
        f"https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={samr_openstd_id}",
        headers=dict(ChainMap({"Host": "openstd.samr.gov.cn"}, HEADERS)),
        timeout=REQUEST_TIMEOUT,
    )
    log_request(response)

    standard_number = findall(r"<h1>标准号：(.+)</h1>", response.text)[0]
    name = findall(r"<td>中文标准名称：<b>(.+)</b></td>", response.text)[0]

    return StandardIdentifier(
        samr_std_id=None,
        samr_openstd_id=samr_openstd_id,
        number=parse_standard_number(standard_number),
        name=name,
    )


def get_identifier_by_number(number: StandardNumber) -> StandardIdentifier:
    """根据 number 获取 identifier"""

    response = get(
        "https://openstd.samr.gov.cn/bzgk/gb/std_list?page=1&pageSize=50"
        f"&p.p90=circulation_date&p.p91=desc&p.p1=0&p.p2={quote(str(number))}",
        headers=dict(ChainMap({"Host": "openstd.samr.gov.cn"}, HEADERS)),
        timeout=REQUEST_TIMEOUT,
    )
    log_request(response)

    samr_openstd_id, new_number = findall(
        r"<a\s+href=\"javascript:void\(0\)\"\s+onclick=\"showInfo\('(\S+)'\);\""
        rf">({str(number).replace('.', r'\.')}[^\d]?.*)</a>",
        response.text,
    )[0]
    name = findall(
        r"<a\s+href=\"javascript:void\(0\)\"\s+style=\"color: gray;\"\s+"
        rf"onclick=\"showInfo\('{samr_openstd_id}'\);\">(.+)</a>",
        response.text,
    )[0]

    return StandardIdentifier(
        samr_std_id=None,
        samr_openstd_id=samr_openstd_id,
        number=parse_standard_number(new_number),
        name=name,
    )


def parse_standard_identifier(identifier: str) -> StandardIdentifier:
    """解析标准编号"""
    # pylint: disable=invalid-name
    SAMR_STD_ID_PATTERN = r"https://std\.samr\.gov\.cn/gb/search/gbDetailed\?id="
    SAMR_OPENSTD_ID_PATTERN = (
        r"http://c\.gb688\.cn/bzgk/gb/showGb\?type="
        r"(?:online|download)&hcno=|https://openstd\.samr\.gov\.cn/bzgk/gb/newGbInfo\?hcno="
    )

    identifier = identifier.strip()

    if bool(match(SAMR_STD_ID_PATTERN, identifier)):
        return get_identifier_by_samr_std_id(sub(SAMR_STD_ID_PATTERN, "", identifier))
    if bool(match(SAMR_OPENSTD_ID_PATTERN, identifier)):
        return get_identifier_by_samr_openstd_id(
            sub(SAMR_OPENSTD_ID_PATTERN, "", identifier)
        )
    if bool(match(r"[A-Z0-9]{32}", identifier)):
        try:
            return get_identifier_by_samr_openstd_id(identifier)
        except Exception:  # pylint: disable=broad-exception-caught
            try:
                return get_identifier_by_samr_std_id(identifier)
            except Exception:
                raise ValueError  # pylint: disable=raise-missing-from
    if bool(match(r"GB/?[TZ]?", identifier)):
        return get_identifier_by_number(parse_standard_number(identifier))

    try:
        return get_identifier_by_number(parse_standard_number(f"GB/T {identifier}"))
    except Exception:  # pylint: disable=broad-exception-caught
        try:
            return get_identifier_by_number(parse_standard_number(f"GB {identifier}"))
        except Exception:  # pylint: disable=broad-exception-caught
            try:
                return get_identifier_by_number(
                    parse_standard_number(f"GB/Z {identifier}")
                )
            except Exception:
                raise ValueError  # pylint: disable=raise-missing-from


def get_captcha_image(
    standard_identifier: StandardIdentifier, session: Optional[Session] = None
):
    """获取验证码"""
    if not session:
        session = Session()

    response = session.get(
        f"http://c.gb688.cn/bzgk/gb/gc?_{int(time() * 1000)}",
        headers=dict(
            ChainMap(
                {
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,"
                    "image/*,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                    "Cache-Control": "",
                    "Dnt": "1",
                    "Host": "c.gb688.cn",
                    "Referer": "http://c.gb688.cn/bzgk/gb/showGb?type=online&"
                    f"hcno={standard_identifier.samr_openstd_id}",
                    "Sec-Ch-Ua": "",
                    "Sec-Ch-Ua-Mobile": "",
                    "Sec-Ch-Ua-Platform": "",
                    "Sec-Fetch-Dest": "",
                    "Sec-Fetch-Mode": "",
                    "Sec-Fetch-Site": "",
                    "Sec-Fetch-User": "",
                    "Upgrade-Insecure-Requests": "",
                },
                HEADERS,
            )
        ),
        timeout=REQUEST_TIMEOUT,
    )
    log_request(response)

    return (session, BytesIO(response.content))


def is_captcha_verified(
    standard_identifier: StandardIdentifier,
    session: Session,
    captcha: str,
) -> bool:
    """验证验证码"""
    response = session.post(
        "http://c.gb688.cn/bzgk/gb/verifyCode",
        headers=dict(
            ChainMap(
                {
                    "Accept": "text/plain, */*; q=0.01",
                    "Accept-Encoding": "gzip, deflate",
                    "Cache-Control": "",
                    "Dnt": "1",
                    "Host": "c.gb688.cn",
                    "Referer": "http://c.gb688.cn/bzgk/gb/showGb?type=online&"
                    f"hcno={standard_identifier.samr_openstd_id}",
                    "Sec-Ch-Ua": "",
                    "Sec-Ch-Ua-Mobile": "",
                    "Sec-Ch-Ua-Platform": "",
                    "Sec-Fetch-Dest": "",
                    "Sec-Fetch-Mode": "",
                    "Sec-Fetch-Site": "",
                    "Sec-Fetch-User": "",
                    "Upgrade-Insecure-Requests": "",
                    "X-Requested-With": "XMLHttpRequest",
                },
                HEADERS,
            )
        ),
        data={"verifyCode": captcha},
        timeout=10,
    )
    log_request(response)

    return response.text == "success"


def download(
    standard_identifier: StandardIdentifier, session: Session, status: StatusContainer
) -> BytesIO:
    """下载标准"""

    def status_request(response: Response):
        color_code = "primary"
        if 200 <= response.status_code < 300:
            color_code = "green"
        elif 300 <= response.status_code < 400:
            color_code = "blue"
        elif 400 <= response.status_code < 600:
            color_code = "red"

        status.markdown(f":{color_code}[{response.status_code}] {response.url}")
        log_request(response)

    response = session.get(
        f"https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno={standard_identifier.samr_openstd_id}",
        headers=dict(ChainMap({"Host": "openstd.samr.gov.cn"}, HEADERS)),
        timeout=REQUEST_TIMEOUT,
    )
    status_request(response)

    if "下载标准" in response.text:
        response = session.get(
            f"http://c.gb688.cn/bzgk/gb/viewGb?hcno={standard_identifier.samr_openstd_id}",
            headers=dict(
                ChainMap(
                    {
                        "Host": "c.gb688.cn",
                        "Referer": "https://openstd.samr.gov.cn/",
                        "Sec-Ch-Ua": "",
                        "Sec-Ch-Ua-Mobile": "",
                        "Sec-Ch-Ua-Platform": "",
                        "Sec-Fetch-Dest": "",
                        "Sec-Fetch-Mode": "",
                        "Sec-Fetch-Site": "",
                        "Sec-Fetch-User": "",
                    },
                    HEADERS,
                )
            ),
            timeout=REQUEST_TIMEOUT,
        )
        status_request(response)

        status.update(label="下载完成", state="complete")
        return BytesIO(response.content)

    response = session.get(
        f"http://c.gb688.cn/bzgk/gb/showGb?type=online&hcno={standard_identifier.samr_openstd_id}",
        headers=dict(
            ChainMap(
                {
                    "Host": "c.gb688.cn",
                    "Referer": "https://openstd.samr.gov.cn/",
                    "Sec-Ch-Ua": "",
                    "Sec-Ch-Ua-Mobile": "",
                    "Sec-Ch-Ua-Platform": "",
                    "Sec-Fetch-Dest": "",
                    "Sec-Fetch-Mode": "",
                    "Sec-Fetch-Site": "",
                    "Sec-Fetch-User": "",
                },
                HEADERS,
            )
        ),
        timeout=REQUEST_TIMEOUT,
    )
    status_request(response)

    html = BeautifulSoup(response.text, "lxml")

    pages = html.find_all(attrs={"class": "page"})

    image_pages: list[Image.Image] = []

    for page in pages:
        background_url = (
            "http://c.gb688.cn/bzgk/gb/viewGbImg?fileName=" + page.attrs["bg"]
        )
        page_width = findall(r"width:(\d+)px", page.attrs["style"])[0]
        page_height = findall(r"height:(\d+)px", page.attrs["style"])[0]
        chunk_width = int(int(page_width) / 10)
        chunk_height = int(int(page_height) / 10)

        response = session.get(
            background_url,
            headers=dict(
                ChainMap(
                    {
                        "Accept": "*/*",
                        "Accept-Encoding": "gzip, deflate",
                        "Cache-Alive": "chunked",
                        "Cache-Control": "no-cache",
                        "Host": urlparse(background_url).netloc,
                        "Pragma": "no-cache",
                        "Referer": "http://c.gb688.cn/bzgk/gb/showGb?type=online"
                        f"&hcno={standard_identifier.samr_openstd_id}",
                        "Sec-Ch-Ua": "",
                        "Sec-Ch-Ua-Mobile": "",
                        "Sec-Ch-Ua-Platform": "",
                        "Sec-Fetch-Dest": "",
                        "Sec-Fetch-Mode": "",
                        "Sec-Fetch-Site": "",
                        "Sec-Fetch-User": "",
                        "Upgrade-Insecure-Requests": "",
                    },
                    HEADERS,
                )
            ),
            timeout=60,
        )
        status_request(response)

        background = Image.open(BytesIO(response.content))
        image_page = Image.new("RGB", (int(page_width), int(page_height)), "white")

        for chunk in page.children:
            if chunk == "\n":
                continue
            if chunk.name != "span":
                raise KeyError()

            chunk_page_x, chunk_page_y = findall(
                r"pdfImg-(\d)-(\d)", chunk.attrs["class"][0]
            )[0]
            chunk_background_x, chunk_background_y = findall(
                r"background-position: -(\d+)px -(\d+)px;", chunk.attrs["style"]
            )[0]
            # print(chunk.attrs["class"][0], chunk.attrs["style"])
            # print(chunk_page_x, chunk_page_y, chunk_background_x, chunk_background_y)

            chunk_image = background.crop(
                (
                    int(chunk_background_x),
                    int(chunk_background_y),
                    int(chunk_background_x) + chunk_width,
                    int(chunk_background_y) + chunk_height,
                )
            )

            image_page.paste(
                chunk_image,
                (int(chunk_page_x) * chunk_width, int(chunk_page_y) * chunk_height),
            )

        image_pages.append(image_page)

    if len(image_pages) < 1:
        raise FileExistsError()

    content = BytesIO()

    image_pages[0].save(
        content, format="pdf", save_all=True, append_images=image_pages[1:]
    )

    status.update(label="下载完成", state="complete")
    return content
