from __future__ import annotations

import pytest

from configpile import types
from configpile.errors import Err


def test_integer() -> None:
    assert types.integer.parse("345") == 345
    assert isinstance(types.integer.parse("qwe"), Err)


def test_separated_by() -> None:
    assert types.integer.separated_by(",").parse("3,4,56") == [3, 4, 56]


def test_word() -> None:
    assert types.word.parse(" test  ") == "test"
