"""Fixture: every handler below re-raises or returns."""


class DBError(Exception):
    pass


class NotFound(Exception):
    pass


class UserMissing(Exception):
    pass


class ParseError(Exception):
    pass


def query():
    raise DBError


def fetch():
    raise NotFound


def parse(path):
    return path


def reraises():
    try:
        query()
    except DBError:  # noqa: TRY203
        raise


def translates():
    try:
        fetch()
    except NotFound as e:
        raise UserMissing() from e


def returns_none(path):
    try:
        return parse(path)
    except ParseError:
        return None


def raises_or_reports(flag):
    try:
        query()
    except DBError:
        if flag:
            raise
        return False
