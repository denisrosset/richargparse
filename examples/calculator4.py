from dataclasses import dataclass
from typing import Sequence

from typing_extensions import Annotated

from configpile import *


@dataclass(frozen=True)
class Calc(Config):
    """
    Command-line tool that sums an arbitrary number of floating point values
    """

    #: Values to sum
    values: Annotated[
        Sequence[float],
        Param.append1(
            types.float_,
            positional=Positional.ZERO_OR_MORE,
            short_flag_name=None,
            long_flag_name=None,
        ),
    ]


c = Calc.from_command_line_()
print(sum(c.values))