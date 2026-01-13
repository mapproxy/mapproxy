# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import TypeVar, Mapping, Hashable, Generic, Iterable, Iterator

V = TypeVar("V")


class ImmutableDictList(Mapping[Hashable, V], Generic[V]):
    """
    A dictionary where each item can also be accessed by the
    integer index of the initial position.

    >>> d = ImmutableDictList([('foo', 23), ('bar', 24)])
    >>> d['bar']
    24
    >>> d[0], d[1]
    (23, 24)
    """

    def __init__(self, items: Iterable[tuple[Hashable, V]]) -> None:
        names: list[Hashable] = []
        values: dict[Hashable, V] = {}

        for name, value in items:
            if name in values:
                raise ValueError(f"Duplicate key: {name!r}")
            names.append(name)
            values[name] = value

        self._names: tuple[Hashable, ...] = tuple(names)
        self._values: dict[Hashable, V] = values

    def __getitem__(self, key: Hashable | int) -> V:
        if isinstance(key, int):
            return self._values[self._names[key]]
        return self._values[key]

    def __iter__(self) -> Iterator[Hashable]:
        # Mapping contract: iteration yields keys
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        contents = ", ".join(
            f"{name!r}: {self._values[name]!r}" for name in self._names
        )
        return f"{self.__class__.__name__}([{contents}])"
