from typing import Iterable, TypeVar, Tuple


def _singleton_repr(self):
    return f"{type(self).__name__}()"


class SingletonMeta(type):
    def __new__(mcs, name, bases, namespace, **kwargs):
        namespace.setdefault("__repr__", _singleton_repr)
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        instance = super().__call__(cls)
        cls._instance = instance
        return cls

    def __call__(cls):
        return cls._instance


T = TypeVar('T')


def pairs(iterable: Iterable[T]) -> Iterable[Tuple[T, T]]:
    it = iter(iterable)
    past = next(it)

    for current in it:
        yield past, current
        past = current