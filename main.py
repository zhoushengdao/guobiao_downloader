"""guobiao downloader"""

from io import BytesIO
from requests import Session
import streamlit as st

from utils import (
    StandardIdentifier,
    download,
    is_captcha_verified,
    parse_standard_identifier,
    get_captcha_image,
)

st.set_page_config(
    page_title="国家标准下载器",
    menu_items={
        # "Get Help": "https://www.extremelycoolapp.com/help",
        # "Report a bug": "https://www.extremelycoolapp.com/bug",
        # "About": "# 国家标准下载器",
    },
)

st.title("国家标准下载器")

STANDARD_IDENTIFIER_HELP = """支持以下格式：
- 完整的标准编号，如 `GB/T 1.1-2020`、`GB 12982-2004`、`GB/Z 43946-2024`
- 标准编号的一部分，如 `1.1-2020`、`GB 12982`、`43946`:red[（注意：这种格式可能查找失败）]
- 国家标准全文公开系统的详细信息页 URL、在线预览页 URL、全文下载页 URL，如：
  - `https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=EB0C64D782BFEE2F77AC6073074BD44E`
  - `http://c.gb688.cn/bzgk/gb/showGb?type=online&hcno=EB0C64D782BFEE2F77AC6073074BD44E`
  - `http://c.gb688.cn/bzgk/gb/showGb?type=download&hcno=EB0C64D782BFEE2F77AC6073074BD44E`
- 全国标准信息公共服务平台的详细信息页 URL，如：`https://std.samr.gov.cn/gb/search/gbDetailed?id=71F772D7F0A2D3A7E05397BE0A0AB82A` :red[（注意：这种格式可能查找失败）]
"""
standard_identifier_str = st.text_input("请输入标准号：", help=STANDARD_IDENTIFIER_HELP)

if standard_identifier_str:
    if (
        "old_standard_identifier_str" in st.session_state
        and st.session_state.old_standard_identifier_str != standard_identifier_str
    ) or "old_standard_identifier_str" not in st.session_state:
        st.session_state.clear()
        st.session_state.old_standard_identifier_str = standard_identifier_str
        st.session_state.captcha_input = ""

    if "standard_identifier" in st.session_state and isinstance(
        st.session_state.standard_identifier, StandardIdentifier
    ):
        standard_identifier = st.session_state.standard_identifier
    else:
        standard_identifier = parse_standard_identifier(standard_identifier_str)
        st.session_state.standard_identifier = standard_identifier

    st.info(f"{standard_identifier.number} {standard_identifier.name}")

    if (
        "session" in st.session_state
        and "captcha_image" in st.session_state
        and isinstance(st.session_state.session, Session)
        and isinstance(st.session_state.captcha_image, BytesIO)
    ):
        session, captcha_image = (
            st.session_state.session,
            st.session_state.captcha_image,
        )
    elif (
        "session" in st.session_state
        and "captcha_image" not in st.session_state
        and isinstance(st.session_state.session, Session)
    ):
        session, captcha_image = get_captcha_image(
            standard_identifier, st.session_state.session
        )
        st.session_state.captcha_image = captcha_image
    else:
        session, captcha_image = get_captcha_image(standard_identifier)
        st.session_state.session = session
        st.session_state.captcha_image = captcha_image

    col1, col2 = st.columns(2)
    with col1:
        st.image(captcha_image, caption="验证码", use_container_width=True)
    with col2:
        captcha_str = st.text_input("请输入验证码：", key="captcha_input")
        st.button(
            "换一个",
            on_click=lambda: st.session_state.pop("old_standard_identifier_str"),
        )

    if captcha_str:
        if is_captcha_verified(standard_identifier, session, captcha_str):
            status = st.status("下载中……")

            try:
                content = download(
                    standard_identifier, session, status
                )  # pylint: disable=too-many-function-args
                st.session_state.download_success = True
            except Exception as err:
                status.update(label="下载失败", state="error")
                raise err

            st.download_button(
                "下载",
                content,
                str(standard_identifier.number).replace("/", "")
                + f" {standard_identifier.name}.pdf",
                use_container_width=True,
            )
        else:
            st.error("验证码错误")
