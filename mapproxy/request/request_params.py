from typing import TypeVar, Generic, Iterable, Iterator, Union
from urllib.parse import quote

from mapproxy.request.no_case_multi_dict import NoCaseMultiDict


V = TypeVar("V")


class RequestParams(Generic[V]):
    """
    Represents key-value request parameters with case-insensitive keys.
    Multiple values for a single key are concatenated.

    >>> qs = RequestParams(dict(foo='egg', bar='ham%eggs', baz=100)).query_string
    >>> sorted(qs.split('&'))
    ['bar=ham%25eggs', 'baz=100', 'foo=egg']
    """

    params: NoCaseMultiDict[V] = NoCaseMultiDict()

    def __init__(self, param: 'Union[dict[str, V]|NoCaseMultiDict[V]|RequestParams|None]' = None, delimiter=','):
        self.delimiter = delimiter
        if isinstance(param, RequestParams):
            self.params = param.params.copy()
        elif isinstance(param, NoCaseMultiDict) or isinstance(param, dict):
            self.params = NoCaseMultiDict(param)
        elif param is not None:
            raise ValueError('param has invalid value')

    def get(self, key, default=None):
        """
        Returns the value for `key` or the `default`.
        """
        return self.params.get(key, default)

    def set(self, key: str, value: V | Iterable[V], *, append: bool = False, unpack: bool = False) -> None:
        self.params.set(key, value, append=append, unpack=unpack)

    def update(self, mapping=(), append=False):
        """
        Update internal request parameters from an iterable of ``(key, value)``
        tuples or a dict.

        If `append` is ``True`` the value will be added to other values for
        this `key`.
        """
        self.params.update_multi(mapping, append=append)

    def __getitem__(self, key: str) -> str:
        return self.delimiter.join(map(str, self.params.get_all(key)))

    def __setitem__(self, key: str, value: V) -> None:
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        if key in self:
            del self.params[key]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self.params

    def __getattr__(self, name: str) -> str:
        if name in self:
            return self[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __iter__(self) -> Iterator[str]:
        for key, _ in self.params.items():
            yield key

    def __str__(self) -> str:
        return self.query_string

    def items(self) -> Iterator[tuple[str, V]]:
        for key, values in self.params.items_multi():
            yield key, self.delimiter.join(str(v) for v in values)

    def copy(self) -> "RequestParams[V]":
        return self.__class__(self.params, delimiter=self.delimiter)

    @property
    def query_string(self) -> str:
        """
        The map request as a query string (the order is not guaranteed).

        >>> qs = RequestParams(dict(foo='egg', bar='ham%eggs', baz=100)).query_string
        >>> sorted(qs.split('&'))
        ['bar=ham%25eggs', 'baz=100', 'foo=egg']
        """
        kv_pairs: list[str] = []

        for key, values in self.params.items_multi():
            value = self.delimiter.join(str(v) for v in values)
            encoded = quote(value.encode("utf-8"), safe=self.delimiter)
            kv_pairs.append(f"{key}={encoded}")

        return "&".join(kv_pairs)

    def with_defaults(self, defaults: "RequestParams[V]") -> "RequestParams[V]":
        """
        Return a copy with values from `defaults` applied unless explicitly set.
        """
        new = self.copy()
        for key, values in defaults.params.items_multi():
            if values != [None]:
                new.set(key, values, unpack=True)
        return new

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.items())!r})"
