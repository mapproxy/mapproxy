from typing import TypeVar, Generic, Iterable, Optional, Callable, Iterator, MutableMapping

V = TypeVar("V")
T = TypeVar("T")


class NoCaseMultiDict(MutableMapping[str, V], Generic[V]):
    """
    Dictionary with case-insensitive keys and support for multiple values
    per key. The first inserted key spelling is preserved.

    >>> d = NoCaseMultiDict([('A', 'b'), ('a', 'c'), ('B', 'f'), ('c', 'x'), ('c', 'y'), ('c', 'z')])
    >>> d['a']
    'b'
    >>> d.get_all('a')
    ['b', 'c']
    >>> 'a' in d and 'b' in d
    True
    """

    def __init__(self, mapping: Iterable[tuple[str, V]] | dict[str, V] | "NoCaseMultiDict[V]" = ()) -> None:
        self._data: dict[str, tuple[str, list[V]]] = {}
        self.update_multi(mapping, append=True)

    def _key(self, key: str) -> str:
        return key.lower()

    def update_multi(self, mapping: Iterable[tuple[str, V]] | dict[str, V] | "NoCaseMultiDict[V]", append: bool = False) -> None:
        if isinstance(mapping, NoCaseMultiDict):
            for key, value in mapping.items_multi():
                self.set(key, value, append=append)
        elif isinstance(mapping, dict):
            for key2, value2 in mapping.items():
                self.set(key2, value2, append=append)
        else:
            for key3, value3 in mapping:
                self.set(key3, value3, append=append)

    def __getitem__(self, key: str) -> V:
        if not self._key(key) in self._data:
            raise KeyError(key) from None

        return self._data[self._key(key)][1][0]

    def __setitem__(self, key: str, value: V) -> None:
        self._data[self._key(key)] = (key, [value])

    def __delitem__(self, key: str) -> None:
        del self._data[self._key(key)]

    def __iter__(self) -> Iterator[str]:
        for original_key, _ in self._data.values():
            yield original_key

    def __len__(self) -> int:
        return len(self._data)

    def __getstate__(self) -> list[tuple[str, V]]:
        return [(k, v) for k, vs in self.items_multi() for v in vs]

    def __setstate__(self, state: Iterable[tuple[str, V]]) -> None:
        self._data = {}
        self.update_multi(state)

    def get_typed(self, key: str, default: Optional[T] = None, type_func: Optional[Callable[[V], T]] = None) -> Optional[V | T]:
        try:
            value = self[key]
            if type_func:
                return type_func(value)
            else:
                return value
        except (KeyError, ValueError):
            return default

    def get_all(self, key: str) -> list[V]:
        return self._data.get(self._key(key), ("", []))[1]

    def set(self, key: str, value: V | Iterable[V], *, append: bool = False, unpack: bool = False) -> None:
        key_l = self._key(key)

        if key_l not in self._data:
            self._data[key_l] = (key, [])

        _, values = self._data[key_l]

        if not append:
            values.clear()

        if unpack:
            values.extend(value)  # type: ignore[arg-type]
        else:
            values.append(value)  # type: ignore[arg-type]

    def items_multi(self) -> Iterator[tuple[str, list[V]]]:
        for key, values in self._data.values():
            yield key, values

    def copy(self) -> "NoCaseMultiDict[V]":
        return NoCaseMultiDict(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({list(self.items_multi())!r})"
