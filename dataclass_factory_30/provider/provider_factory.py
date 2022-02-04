from types import MethodType, BuiltinMethodType, WrapperDescriptorType
from typing import TypeVar, Type, overload, Any, Callable, Tuple, Union

from .essential import Provider
from .provider_basics import create_req_checker, LimitingProvider, foreign_parser, ValueProvider
from .request_cls import (
    SerializerRequest, ParserRequest,
)
from ..common import Parser, Serializer

T = TypeVar('T')


def resolve_classmethod(func) -> Tuple[type, Callable]:
    if isinstance(func, (MethodType, BuiltinMethodType)):
        bound = func.__self__
    elif isinstance(func, WrapperDescriptorType):
        bound = func.__objclass__
    else:
        raise ValueError

    if not isinstance(bound, type):
        raise ValueError

    return bound, func


def _resolve_as_args(func_or_pred, maybe_func) -> Tuple[Any, Any]:
    func: Any
    if maybe_func is None:
        if isinstance(func_or_pred, type):
            pred = func_or_pred
            func = func_or_pred
        else:
            pred, func = resolve_classmethod(func_or_pred)
    else:
        pred = func_or_pred
        func = maybe_func

    return pred, func


@overload
def as_parser(func_or_pred: Type[T], func: Parser[T]) -> Provider:
    pass


@overload
def as_parser(func_or_pred: Any, func: Parser) -> Provider:
    pass


@overload
def as_parser(func_or_pred: Union[type, Parser]) -> Provider:
    pass


def as_parser(func_or_pred, func=None):
    pred, func = _resolve_as_args(func_or_pred, func)
    return LimitingProvider(
        create_req_checker(pred),
        ValueProvider(
            ParserRequest,
            foreign_parser(func)
        )
    )


@overload
def as_serializer(pred: Type[T], func: Serializer[T]) -> Provider:
    pass


@overload
def as_serializer(pred: Any, func: Serializer) -> Provider:
    pass


# We can get origin class if WrapperDescriptorType has passed,
# but it is a rare case, so one arg signature was removed
def as_serializer(pred, func):
    return LimitingProvider(
        create_req_checker(pred),
        ValueProvider(
            SerializerRequest,
            func
        )
    )


@overload
def as_constructor(func_or_pred: Type[T], constructor: Callable[..., T]) -> Provider:
    pass


@overload
def as_constructor(func_or_pred: Any, constructor: Callable) -> Provider:
    pass


@overload
def as_constructor(func_or_pred: Callable) -> Provider:
    pass


# TODO: make as_constructor
def as_constructor(func_or_pred, constructor=None):
    pass