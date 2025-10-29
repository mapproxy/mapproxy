# SPDX-License-Identifier: MIT
# Copyright (C) pygeoapi developers

# Below is strongly derived from pygeoapi/util.py

import base64
import dateutil
import json
import pathlib
import uuid
from babel.support import Translations
from datetime import date, datetime, time
from decimal import Decimal
from importlib import resources as importlib_resources
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.exceptions import TemplateNotFound
from pathlib import Path
from typing import Any, Optional

from mapproxy.config.config import base_config
from mapproxy.version import __version__

import logging

LOGGER = logging.getLogger(__name__)

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def json_serial(obj: Any) -> Any:
    """
    helper function to convert to JSON non-default
    types (source: https://stackoverflow.com/a/22238613)

    :param obj: `object` to be evaluated

    :returns: JSON non-default type to `str`
    """

    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        try:
            LOGGER.debug("Returning as UTF-8 decoded bytes")
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            LOGGER.debug("Returning as base64 encoded JSON object")
            return base64.b64encode(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif type(obj).__name__ in ["int32", "int64"]:
        return int(obj)
    elif type(obj).__name__ in ["float32", "float64"]:
        return float(obj)
    elif isinstance(obj, (pathlib.PurePath, Path)):
        return str(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    else:
        msg = f"{obj} type {type(obj)} not serializable"
        LOGGER.error(msg)
        raise TypeError(msg)


def to_json(dict_: dict, pretty: bool = False) -> str:
    """
    Serialize dict to json

    :param dict_: `dict` of JSON representation
    :param pretty: `bool` of whether to prettify JSON (default is `False`)

    :returns: JSON string representation
    """

    if pretty:
        indent = 4
    else:
        indent = None

    return json.dumps(dict_, default=json_serial, indent=indent, separators=(",", ":"))


def format_datetime(value: str, format_: str = DATETIME_FORMAT) -> str:
    """
    Parse datetime as ISO 8601 string; re-present it in particular format
    for display in HTML

    :param value: `str` of ISO datetime
    :param format_: `str` of datetime format for strftime

    :returns: string
    """

    if not isinstance(value, str) or not value.strip():
        return ""

    return dateutil.parser.isoparse(value).strftime(format_)


def human_size(nbytes: int) -> str:
    """
    Provides human readable file size

    source: https://stackoverflow.com/a/14996816

    :param nbytes: int of file size (bytes)
    :param units: list of unit abbreviations

    :returns: string of human readable filesize
    """

    suffixes = ["B", "K", "M", "G", "T", "P"]

    fnbytes = float(nbytes)
    i = 0

    while fnbytes >= 1024 and i < len(suffixes) - 1:
        fnbytes /= 1024.0
        i += 1

    if suffixes[i] == "K":
        f = str(int(fnbytes)).rstrip("0").rstrip(".")
    elif suffixes[i] == "B":
        return str(fnbytes)
    else:
        f = f"{fnbytes:.1f}".rstrip("0").rstrip(".")

    return f"{f}{suffixes[i]}"


def get_path_basename(urlpath: str) -> str:
    """
    Helper function to derive file basename

    :param urlpath: URL path

    :returns: string of basename of URL path
    """

    return Path(urlpath).name


def get_breadcrumbs(urlpath: str) -> list:
    """
    helper function to make breadcrumbs from a URL path

    :param urlpath: URL path

    :returns: `list` of `dict` objects of labels and links
    """

    links = []

    tokens = urlpath.split("/")

    s = ""
    for t in tokens:
        if s:
            s += "/" + t
        else:
            s = t
        links.append(
            {
                "href": s,
                "title": t,
            }
        )

    return links


def filter_dict_by_key_value(dict_: dict, key: str, value: str) -> dict:
    """
    helper function to filter a dict by a dict key

    :param dict_: ``dict``
    :param key: dict key
    :param value: dict key value

    :returns: filtered ``dict``
    """

    return {k: v for (k, v) in dict_.items() if v[key] == value}


def render_j2_template(
    config: dict,
    module_name: str,
    template_root: str,
    template_path: str,
    data: dict,
    locale_: Optional[str] = None,
) -> str:
    """
    render Jinja2 template

    :param config: dict of configuration
    :param module_name: module name from which to get templates
    :param template_root: template (relative path to module_name)
    :param template_path: template (relative path to template_root)
    :param data: dict of data
    :param locale_: the requested output Locale

    :returns: string of rendered template
    """

    if base_config().template_dir:
        template_dir = base_config().template_dir + "/" + template_root
    else:
        template_dir = (
            importlib_resources.files(module_name)
            .joinpath("templates")
            .joinpath(template_root)
        )

    template_paths = [template_dir]

    env = Environment(
        loader=FileSystemLoader(template_paths),
        extensions=["jinja2.ext.i18n"],
        autoescape=select_autoescape(),
    )

    env.filters["to_json"] = to_json
    env.filters["format_datetime"] = format_datetime
    env.filters["human_size"] = human_size
    env.globals.update(to_json=to_json)

    env.filters["get_path_basename"] = get_path_basename
    env.globals.update(get_path_basename=get_path_basename)

    env.filters["get_breadcrumbs"] = get_breadcrumbs
    env.globals.update(get_breadcrumbs=get_breadcrumbs)

    env.filters["filter_dict_by_key_value"] = filter_dict_by_key_value
    env.globals.update(filter_dict_by_key_value=filter_dict_by_key_value)

    locale_dir = "."
    translations = Translations.load(locale_dir, [locale_] if locale_ is not None else [])
    env.install_gettext_translations(translations)

    try:
        template = env.get_template(template_path)
    except TemplateNotFound:
        LOGGER.debug(f"template {template_path} not found")
        raise

    return template.render(
        config=config,
        data=data,
        locale=locale_,
        version=__version__,
    )
