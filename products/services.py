import ipaddress
import json
import re
import socket
import ssl
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

import certifi


MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 8


class ProductPreviewError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


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
        redirect_url = urljoin(req.full_url, newurl)
        validate_public_url(redirect_url)
        return super().redirect_request(req, fp, code, msg, headers, redirect_url)


class ProductMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}
        self.title_parts = []
        self.json_ld_parts = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "meta":
            key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
            content = attrs.get("content")
            if key and content:
                self.metadata.setdefault(key.lower(), content.strip())
        elif tag.lower() == "title":
            self._in_title = True
        elif tag.lower() == "script" and "ld+json" in attrs.get("type", "").lower():
            self._in_json_ld = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False
        elif tag.lower() == "script" and self._in_json_ld:
            self._in_json_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self.json_ld_parts.append(data)


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


def extract_json_ld(parser):
    names = []
    prices = []
    images = []
    for raw in parser.json_ld_parts:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in iter_json_objects(data):
            item_type = item.get("@type", "")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "Product" in types:
                if item.get("name"):
                    names.append(str(item["name"]).strip())
                image = item.get("image")
                if isinstance(image, list) and image:
                    image = image[0]
                if isinstance(image, dict):
                    image = image.get("url")
                if image:
                    images.append(str(image))
            if item.get("price") is not None:
                prices.append(item["price"])
    return names, prices, images


def extract_product_metadata(html, final_url):
    parser = ProductMetadataParser()
    parser.feed(html)
    json_names, json_prices, json_images = extract_json_ld(parser)

    name = next(
        (
            value
            for value in [
                parser.metadata.get("og:title"),
                parser.metadata.get("twitter:title"),
                parser.metadata.get("name"),
                *json_names,
                " ".join(parser.title_parts).strip(),
            ]
            if value
        ),
        None,
    )
    price = next(
        (
            parsed
            for value in [
                parser.metadata.get("product:price:amount"),
                parser.metadata.get("og:price:amount"),
                parser.metadata.get("price"),
                *json_prices,
            ]
            if (parsed := parse_price(value)) is not None
        ),
        None,
    )
    image = next(
        (
            value
            for value in [
                parser.metadata.get("og:image"),
                parser.metadata.get("twitter:image"),
                *json_images,
            ]
            if value
        ),
        "",
    )

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
    validate_public_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; CHOEZY/1.0)",
            "Accept": "text/html,application/xhtml+xml",
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
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise ProductPreviewError(
            "PRODUCT_FETCH_FAILED",
            "상품 페이지를 불러오지 못했습니다. 직접 입력해주세요.",
        ) from error
