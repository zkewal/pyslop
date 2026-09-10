"""Fixture: every handler below swallows without raising or returning."""

import logging

log = logging.getLogger(__name__)


class DBError(Exception):
    pass


def query():
    raise DBError


def process(path):
    return path


def fallback():
    return None


def log_only():
    try:
        query()
    except DBError as e:
        print(e)


def silent_pass():
    try:
        query()
    except DBError:
        pass


def skip_on_error(paths):
    for path in paths:
        try:
            process(path)
        except OSError:
            continue


def log_and_continue():
    try:
        query()
    except DBError:
        log.exception("query failed")


def nested_swallow():
    try:
        query()
    except DBError:
        try:
            fallback()
        except OSError:
            pass
