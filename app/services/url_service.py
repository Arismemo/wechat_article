from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


DROP_QUERY_KEYS = {
    "abtest_cookie",
    "acctmode",
    "appmsg_token",
    "ascene",
    "chksm",
    "clicktime",
    "devicetype",
    "enterid",
    "exportkey",
    "fontgear",
    "from",
    "isappinstalled",
    "lang",
    "nettype",
    "scene",
    "sessionid",
    "sharefrom",
    "shareto",
    "subscene",
    "version",
    "wx_header",
    "wxfrom",
}

DROP_QUERY_PREFIXES = ("utm_",)


def normalize_url(raw_url: str) -> str:
    parsed = urlparse(raw_url.strip())
    filtered_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        lower_key = key.lower()
        if lower_key in DROP_QUERY_KEYS:
            continue
        if lower_key.startswith(DROP_QUERY_PREFIXES):
            continue
        filtered_query.append((key, value))

    query = urlencode(sorted(filtered_query))
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
        query=query,
    )
    return urlunparse(normalized)


def detect_source_type(url: str) -> str:
    parsed = urlparse(url)
    if "mp.weixin.qq.com" in parsed.netloc:
        return "wechat"
    return "web"
