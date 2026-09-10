from typing import TypedDict, Unpack


class TourOpts(TypedDict):
    title: str


def public_typed(**kwargs: Unpack[TourOpts]):
    return kwargs


def _private_passthrough(**kwargs):
    return kwargs


def no_kwargs_here(title: str):
    return title
