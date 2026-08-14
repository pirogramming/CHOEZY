import ipaddress
import json
import re
import socket
import ssl
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import certifi


MAX_RESPONSE_BYTES = 3_000_000
REQUEST_TIMEOUT_SECONDS = 8

NAME_KEYS = (
    "productName",
    "product_name",
    "itemName",
    "item_name",
    "name",
    "title",
)
PRICE_KEYS = (
    "salePrice",
    "sale_price",
    "discountPrice",
    "discount_price",
    "finalPrice",
    "final_price",
    "lowPrice",
    "low_price",
    "price",
)


class ProductPreviewError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_url(url):
    """브라우저에 붙여 넣는 한글 URL을 HTTP 요청 가능한 형태로 바꿉니다."""
    try:
        parsed = urlsplit(url.strip())
        hostname = parsed.hostname.encode("idna").decode("ascii")
        port = f":{parsed.port}" if parsed.port else ""
    except (AttributeError, UnicodeError, ValueError) as error:
        raise ProductPreviewError(
            "INVALID_URL",
            "유효한 상품 URL을 입력해주세요.",
        ) from error

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    return urlunsplit(
        (
            parsed.scheme.lower(),
            f"{hostname}{port}",
            quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
            quote(parsed.query, safe="=&%/:?@!$'()*+,;[]-._~"),
            "",
        )
    )


def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProductPreviewError("INVALID_URL", "유효한 상품 URL을 입력해주세요.")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(parsed.hostname, port)
    except socket.gaierror as error:
        raise ProductPreviewError(
            "URL_NOT_REACHABLE",
            "상품 URL의 주소를 확인할 수 없습니다.",
        ) from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ProductPreviewError(
                "PRIVATE_URL_NOT_ALLOWED",
                "내부 네트워크 주소는 조회할 수 없습니다.",
            )


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_url = normalize_url(urljoin(req.full_url, newurl))
        validate_public_url(redirect_url)
        return super().redirect_request(req, fp, code, msg, headers, redirect_url)


class ProductMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}
        self.title_parts = []
        self.json_scripts = []
        self.microdata = {}
        self._in_title = False
        self._script_type = ""
        self._script_parts = []
        self._microdata_key = ""
        self._microdata_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value is not None}
        tag = tag.lower()
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
            content = attrs.get("content")
            if key and content:
                self.metadata.setdefault(key.lower(), content.strip())
        if attrs.get("itemprop"):
            key = attrs["itemprop"].lower()
            value = (
                attrs.get("content")
                or attrs.get("value")
                or attrs.get("href")
                or attrs.get("src")
            )
            if value:
                self.microdata.setdefault(key, value.strip())
            elif key in {"name", "price"}:
                self._microdata_key = key
                self._microdata_parts = []
        if tag == "title":
            self._in_title = True
        elif tag == "script":
            script_type = attrs.get("type", "").lower()
            if "json" in script_type:
                self._script_type = script_type
                self._script_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._script_type:
            raw = "".join(self._script_parts).strip()
            if raw:
                self.json_scripts.append((self._script_type, raw))
            self._script_type = ""
            self._script_parts = []
        if self._microdata_key:
            value = "".join(self._microdata_parts).strip()
            if value:
                self.microdata.setdefault(self._microdata_key, value)
            self._microdata_key = ""
            self._microdata_parts = []

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._script_type:
            self._script_parts.append(data)
        if self._microdata_key:
            self._microdata_parts.append(data)


def iter_json_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)


def parse_price(value):
    if value is None:
        return None
    normalized = re.sub(r"[^0-9.]", "", str(value))
    if not normalized:
        return None
    try:
        price = int(Decimal(normalized))
    except (InvalidOperation, ValueError):
        return None
    return price if price > 0 else None


def normalized_type(value):
    item_type = value.get("@type", "") if isinstance(value, dict) else ""
    types = item_type if isinstance(item_type, list) else [item_type]
    return {str(item).lower() for item in types}


def first_mapping_value(item, keys):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def image_url(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = first_mapping_value(value, ("url", "contentUrl"))
    return str(value).strip() if value else ""


def product_candidate(item):
    """구조화 데이터 객체 하나에서 서로 짝이 맞는 상품 정보를 찾습니다."""
    if not isinstance(item, dict):
        return None

    types = normalized_type(item)
    has_product_type = "product" in types
    name = first_mapping_value(item, NAME_KEYS)
    price = first_mapping_value(item, PRICE_KEYS)

    offers = item.get("offers")
    if isinstance(offers, list):
        offers = next((offer for offer in offers if isinstance(offer, dict)), None)
    if isinstance(offers, dict):
        price = price or first_mapping_value(offers, PRICE_KEYS)
        price_specification = offers.get("priceSpecification")
        if price is None and isinstance(price_specification, dict):
            price = first_mapping_value(price_specification, PRICE_KEYS)

    # 일반 사이트의 application/json도 지원하되, 무관한 name/price 쌍은
    # 상품 객체로 오인하지 않도록 상품을 나타내는 단서가 있어야 합니다.
    product_hint = has_product_type or any(
        key in item
        for key in (
            "productName",
            "product_name",
            "itemName",
            "item_name",
            "offers",
            "sku",
            "productId",
            "productNo",
        )
    )
    parsed_price = parse_price(price)
    if not product_hint or not name or parsed_price is None:
        return None
    return {
        "name": str(name).strip(),
        "price": parsed_price,
        "image": image_url(
            first_mapping_value(item, ("image", "imageUrl", "image_url", "thumbnailUrl"))
        ),
        "structured": has_product_type,
    }


def extract_json_products(parser):
    candidates = []
    for script_type, raw in parser.json_scripts:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in iter_json_objects(data):
            candidate = product_candidate(item)
            if candidate:
                candidate["json_ld"] = "ld+json" in script_type
                candidates.append(candidate)
    return candidates


def first_value(values):
    return next((value for value in values if value not in (None, "")), None)


def decode_json_text(value):
    try:
        return json.loads(f'"{value}"').strip()
    except (json.JSONDecodeError, AttributeError):
        return value.strip()


def extract_unique_embedded_values(html):
    """완전한 JSON이 아닌 초기 상태 스크립트의 단일 상품값을 찾습니다.

    여러 상품이 섞인 목록 페이지에서는 값을 고르지 않아 잘못된 자동 입력을
    방지합니다.
    """
    names = {
        decode_json_text(value)
        for value in re.findall(
            r'"(?:productName|product_name|itemName|item_name)"\s*:\s*"((?:\\.|[^"\\])+)"',
            html,
            flags=re.IGNORECASE,
        )
        if value.strip()
    }
    prices = {
        parsed
        for value in re.findall(
            r'"(?:salePrice|sale_price|discountPrice|discount_price|finalPrice|final_price)"\s*:\s*"?([0-9][0-9,.]*)',
            html,
            flags=re.IGNORECASE,
        )
        if (parsed := parse_price(value)) is not None
    }
    return (
        next(iter(names)) if len(names) == 1 else None,
        next(iter(prices)) if len(prices) == 1 else None,
    )


def extract_product_metadata(html, final_url):
    parser = ProductMetadataParser()
    parser.feed(html)
    candidates = extract_json_products(parser)
    structured = next(
        (
            candidate
            for candidate in candidates
            if candidate["structured"] or candidate["json_ld"]
        ),
        None,
    )
    embedded = candidates[0] if candidates else None
    fallback_name, fallback_price = extract_unique_embedded_values(html)

    name = first_value(
        [
            structured and structured["name"],
            parser.metadata.get("og:title"),
            parser.metadata.get("twitter:title"),
            parser.metadata.get("name"),
            parser.microdata.get("name"),
            embedded and embedded["name"],
            fallback_name,
            " ".join(parser.title_parts).strip(),
        ]
    )
    price = next(
        (
            parsed
            for value in [
                structured and structured["price"],
                parser.metadata.get("product:price:amount"),
                parser.metadata.get("og:price:amount"),
                parser.metadata.get("product:price"),
                parser.metadata.get("price"),
                parser.microdata.get("price"),
                embedded and embedded["price"],
                fallback_price,
            ]
            if (parsed := parse_price(value)) is not None
        ),
        None,
    )
    image = first_value(
        [
            structured and structured["image"],
            parser.metadata.get("og:image"),
            parser.metadata.get("twitter:image"),
            parser.microdata.get("image"),
            embedded and embedded["image"],
        ]
    ) or ""

    if not name or price is None:
        raise ProductPreviewError(
            "PRODUCT_INFO_NOT_FOUND",
            "상품명 또는 가격을 찾지 못했습니다. 직접 입력해주세요.",
        )

    return {
        "product_name": name[:200],
        "product_price": price,
        "image_url": urljoin(final_url, image) if image else "",
        "product_url": final_url,
    }


def fetch_product_preview(url):
    url = normalize_url(url)
    validate_public_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        response = build_opener(
            SafeRedirectHandler(),
            HTTPSHandler(context=ssl_context),
        ).open(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ProductPreviewError(
                "UNSUPPORTED_CONTENT",
                "상품 페이지 형식만 조회할 수 있습니다.",
            )
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProductPreviewError(
                "RESPONSE_TOO_LARGE",
                "상품 페이지의 크기가 너무 큽니다.",
            )
        charset = response.headers.get_content_charset() or "utf-8"
        html = body.decode(charset, errors="replace")
        return extract_product_metadata(html, response.geturl())
    except ProductPreviewError:
        raise
    except HTTPError as error:
        if error.code in {403, 429}:
            raise ProductPreviewError(
                "SITE_ACCESS_BLOCKED",
                "해당 쇼핑몰이 자동 조회를 제한하고 있습니다. 상품명과 가격을 직접 입력해주세요.",
            ) from error
        raise ProductPreviewError(
            "PRODUCT_FETCH_FAILED",
            "상품 페이지를 불러오지 못했습니다. 직접 입력해주세요.",
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ProductPreviewError(
            "PRODUCT_FETCH_FAILED",
            "상품 페이지를 불러오지 못했습니다. 직접 입력해주세요.",
        ) from error
