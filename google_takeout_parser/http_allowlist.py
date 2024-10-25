"""
For context, see: https://github.com/purarue/google_takeout_parser/issues/31

This converts HTTP URLs to HTTPS, if they're from certain google domains.
In some cases URLs in the takeout are HTTP for no reason, and converting them
to HTTPs is nicer for downstream consumers, e.g. to dedupe, parsing from multiple
sources
"""

import logging
from typing import Set, Optional

from .log import logger

from urllib.parse import urlsplit, urlunsplit

CONVERT_HTTP: Set[str] = set()

# anything that ends with these domains
# curl -sL 'https://www.google.com/supported_domains
CONVERT_HTTP_SUFFIX: Set[str] = {
    "youtube.com",
    "bp0.blogger.com",
    "google.com",
    "google.ad",
    "google.ae",
    "google.com.af",
    "google.com.ag",
    "google.al",
    "google.am",
    "google.co.ao",
    "google.com.ar",
    "google.as",
    "google.at",
    "google.com.au",
    "google.az",
    "google.ba",
    "google.com.bd",
    "google.be",
    "google.bf",
    "google.bg",
    "google.com.bh",
    "google.bi",
    "google.bj",
    "google.com.bn",
    "google.com.bo",
    "google.com.br",
    "google.bs",
    "google.bt",
    "google.co.bw",
    "google.by",
    "google.com.bz",
    "google.ca",
    "google.cd",
    "google.cf",
    "google.cg",
    "google.ch",
    "google.ci",
    "google.co.ck",
    "google.cl",
    "google.cm",
    "google.cn",
    "google.com.co",
    "google.co.cr",
    "google.com.cu",
    "google.cv",
    "google.com.cy",
    "google.cz",
    "google.de",
    "google.dj",
    "google.dk",
    "google.dm",
    "google.com.do",
    "google.dz",
    "google.com.ec",
    "google.ee",
    "google.com.eg",
    "google.es",
    "google.com.et",
    "google.fi",
    "google.com.fj",
    "google.fm",
    "google.fr",
    "google.ga",
    "google.ge",
    "google.gg",
    "google.com.gh",
    "google.com.gi",
    "google.gl",
    "google.gm",
    "google.gr",
    "google.com.gt",
    "google.gy",
    "google.com.hk",
    "google.hn",
    "google.hr",
    "google.ht",
    "google.hu",
    "google.co.id",
    "google.ie",
    "google.co.il",
    "google.im",
    "google.co.in",
    "google.iq",
    "google.is",
    "google.it",
    "google.je",
    "google.com.jm",
    "google.jo",
    "google.co.jp",
    "google.co.ke",
    "google.com.kh",
    "google.ki",
    "google.kg",
    "google.co.kr",
    "google.com.kw",
    "google.kz",
    "google.la",
    "google.com.lb",
    "google.li",
    "google.lk",
    "google.co.ls",
    "google.lt",
    "google.lu",
    "google.lv",
    "google.com.ly",
    "google.co.ma",
    "google.md",
    "google.me",
    "google.mg",
    "google.mk",
    "google.ml",
    "google.com.mm",
    "google.mn",
    "google.com.mt",
    "google.mu",
    "google.mv",
    "google.mw",
    "google.com.mx",
    "google.com.my",
    "google.co.mz",
    "google.com.na",
    "google.com.ng",
    "google.com.ni",
    "google.ne",
    "google.nl",
    "google.no",
    "google.com.np",
    "google.nr",
    "google.nu",
    "google.co.nz",
    "google.com.om",
    "google.com.pa",
    "google.com.pe",
    "google.com.pg",
    "google.com.ph",
    "google.com.pk",
    "google.pl",
    "google.pn",
    "google.com.pr",
    "google.ps",
    "google.pt",
    "google.com.py",
    "google.com.qa",
    "google.ro",
    "google.ru",
    "google.rw",
    "google.com.sa",
    "google.com.sb",
    "google.sc",
    "google.se",
    "google.com.sg",
    "google.sh",
    "google.si",
    "google.sk",
    "google.com.sl",
    "google.sn",
    "google.so",
    "google.sm",
    "google.sr",
    "google.st",
    "google.com.sv",
    "google.td",
    "google.tg",
    "google.co.th",
    "google.com.tj",
    "google.tl",
    "google.tm",
    "google.tn",
    "google.to",
    "google.com.tr",
    "google.tt",
    "google.com.tw",
    "google.co.tz",
    "google.com.ua",
    "google.co.ug",
    "google.co.uk",
    "google.com.uy",
    "google.co.uz",
    "google.com.vc",
    "google.co.ve",
    "google.co.vi",
    "google.com.vn",
    "google.vu",
    "google.ws",
    "google.rs",
    "google.co.za",
    "google.co.zm",
    "google.co.zw",
    "google.cat",
}


def _convert_to_https(url: str, logger: Optional[logging.Logger] = None) -> str:
    uu = urlsplit(url)
    if uu.scheme == "http":
        without_www = uu.netloc[4:] if uu.netloc.startswith("www.") else uu.netloc
        if without_www in CONVERT_HTTP or without_www in CONVERT_HTTP_SUFFIX:
            return urlunsplit(("https",) + uu[1:])
        # check if this is a subdomain of a domain in the allowlist
        # like m.youtube.com
        if any(without_www.endswith("." + suffix) for suffix in CONVERT_HTTP_SUFFIX):
            return urlunsplit(("https",) + uu[1:])
        if logger:
            logger.debug(
                "HTTP URL did not match allowlist: %s\nIf you think this should be auto-converted to HTTPS, make an issue here: https://github.com/purarue/google_takeout_parser/issues/new",
                url,
            )
    # some other scheme, just return
    return url


def _convert_to_https_opt(
    url: Optional[str], logger: Optional[logging.Logger] = None
) -> Optional[str]:
    if url is None:
        return None
    return _convert_to_https(url, logger)


def convert_to_https(url: str) -> str:
    return _convert_to_https(url, logger=logger)


def convert_to_https_opt(url: Optional[str]) -> Optional[str]:
    return _convert_to_https_opt(url, logger=logger)
