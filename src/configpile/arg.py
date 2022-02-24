from __future__ import annotations

import abc
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from .collector import Collector
from .types import ArgType

T = TypeVar("T", covariant=True)  #: Item type

W = TypeVar("W", covariant=True)  #: Wrapped item type

if TYPE_CHECKING:
    from .config import Config


class AutoArgName(Enum):
    """
    Describes automatic handling of an argument name
    """

    #: The argument should not be present in the corresponding source
    FORBIDDEN = 0

    #: Derives the argument name from the original Python identifier (default)
    DERIVED = 1


ArgName = Union[str, AutoArgName]


@dataclass(frozen=True)
class BaseArg(abc.ABC):
    """
    Base class for command line arguments
    """

    help: Optional[str] = None  #: Help for the argument

    #: Short option name, used in command line parsing, prefixed by a single hyphen
    short_flag_name: Optional[str] = None

    #: Long option name used in command line argument parsing
    #:
    #: It is lowercase, prefixed with ``--`` and words are separated by hyphens
    long_flag_name: ArgName = AutoArgName.DERIVED

    def all_flags(self) -> Sequence[str]:
        """
        Returns a sequence of all forms of command line flags
        """
        res: List[str] = []
        if self.short_flag_name is not None:
            res.append(self.short_flag_name)
        assert self.long_flag_name != AutoArgName.DERIVED
        if isinstance(self.long_flag_name, str):
            res.append(self.long_flag_name)
        return res

    def updated_dict_(self, name: str, help: str, env_prefix: Optional[str]) -> Mapping[str, Any]:
        """
        Returns updated values for this argument, used during :class:`.App` construction

        Args:
            name: Argument field name
            help: Argument docstring which describes the argument role
            env_prefix: Uppercase prefix for all environment variables

        Returns:

        """
        res = {"name": name, "help": help}
        if self.long_flag_name == AutoArgName.DERIVED:
            res["long_flag_name"] = "--" + name.replace("_", "-")
        return res

    def updated(self, name: str, help: str, env_prefix: Optional[str]) -> BaseArg:
        return dataclasses.replace(self, **self.updated_dict_(name, help, env_prefix))

    def argparse_argument_kwargs(self) -> Mapping[str, Any]:
        """
        Returns the keyword arguments for use with argparse.ArgumentParser.add_argument

        Returns:
            Keyword arguments mapping
        """
        return {"help": self.help}


@dataclass(frozen=True)
class Cmd(BaseArg):
    """
    Command flag that expands into a flag/value pair
    """

    new_flag: str = ""  #: Inserted flag in the command line
    new_value: str = ""  #: Inserted value in the command line

    def inserts(self) -> Tuple[str, str]:
        """
        Returns the flag/value pair that is inserted when this command flag is present
        """
        return (self.new_flag, self.new_value)

    def updated(self, name: str, help: str, env_prefix: Optional[str]) -> Cmd:
        return dataclasses.replace(self, **self.updated_dict_(name, help, env_prefix))

    @staticmethod
    def cmd(
        new_flag: str,
        new_value: str,
        *,
        short_flag_name: Optional[str],
        long_flag_name: ArgName = AutoArgName.DERIVED,
    ) -> Cmd:
        """
        Constructs a command line flag that inserts a flag/value pair in the command line

        At least one of ``short_flag_name`` or ``long_flag_name`` must be defined.

        Args:
            new_flag: Inserted flag, including the hyphen prefix
            new_value: String value to insert following the flag
            short_flag_name: Short flag name of this command flag
            long_flag_name: Long flag name of this command flag
        """
        res = Cmd(
            new_flag=new_flag,
            new_value=new_value,
            short_flag_name=short_flag_name,
            long_flag_name=long_flag_name,
        )
        assert res.all_flags(), "Provide at least one of short_flag_name or long_flag_name"
        return res


class Positional(Enum):
    """
    Describes the positional behavior of an arg
    """

    FORBIDDEN = 0  #: The argument is not positional
    ONCE = 1  #: The argument parses a single positional value
    ZERO_OR_MORE = 2  #: The argument parses the remaining positional value
    ONE_OR_MORE = 3  #: The argument parses at least one remaining positional value

    def should_be_last(self) -> bool:
        """
        Returns whether this positional arg should be the last one
        """
        return self in {Positional.ZERO_OR_MORE, Positional.ONE_OR_MORE}

    def is_positional(self) -> bool:
        """
        Returns whether this arg is positional
        """
        return self != Positional.FORBIDDEN


@dataclass(frozen=True)
class Arg(BaseArg, Generic[T]):
    """
    Describes a configuration argument

    Instances have two "states":

    * Initially, instances of :class:`.Arg` are assigned to class attributes of
      subclasses of :class:`.App`. In that state, :attr:`.Arg.name` is not set,
      and the other ``..._name`` attributes contain either a custom name, or
      instructions about the derivation of the corresponding name.

    * When an instance of :class:`.App` is constructed, the ``..._name`` fields of the
      instance are populated with updated instances of :class:`.Arg`.
    """

    #: Argument type, parser from string to value
    arg_type: ArgType[T] = ArgType.invalid()

    #: Argument collector
    collector: Collector[T] = Collector.invalid()  # type: ignore

    default_value: Optional[str] = None  #: Default value inserted as instance

    name: Optional[str] = None  #: Python identifier representing the argument

    positional: Positional = Positional.FORBIDDEN

    #: Configuration key name used in INI files
    #:
    #: It is lowercase, and words are separated by hyphens.
    config_key_name: ArgName = AutoArgName.DERIVED

    #: Environment variable name
    #:
    #: The environment variable name has an optional prefix, followed by the
    #: Python identifier in uppercase, with underscore as separator.
    #:
    #: This prefix is provided by :attr:`.App.env_prefix_`
    #:
    #: If a non-empty prefix is given, the name is prefixed with it
    #: (and an underscore).
    env_var_name: ArgName = AutoArgName.FORBIDDEN

    def __call__(self, config: Config) -> T:
        assert self.name is not None, "Needs a constructed App instance to read values from"
        return cast(T, config.values[self.name])

    def updated(self, name: str, help: str, env_prefix: Optional[str]) -> Arg[T]:
        return dataclasses.replace(self, **self.replacements(name, help, env_prefix))

    def replacements(self, name: str, help: str, env_prefix: Optional[str]) -> Mapping[str, Any]:
        r = dict(super().updated_dict_(name, help, env_prefix))
        if self.config_key_name == AutoArgName.DERIVED:
            r["config_key_name"] = name.replace("_", "-")
        if self.env_var_name == AutoArgName.DERIVED and env_prefix is not None:
            if env_prefix:
                r["env_var_name"] = env_prefix + "_" + name.upper()
            else:
                r["env_var_name"] = name.upper()
        return r

    def all_config_key_names(self) -> Sequence[str]:
        """
        Returns a sequence of all forms of command line options

        Returns:
            Command line options
        """
        if isinstance(self.config_key_name, str):
            return [self.config_key_name]
        else:
            return []

    def all_env_var_names(self) -> Sequence[str]:
        """
        Returns a sequence of all forms of command line options

        Returns:
            Command line options
        """
        if isinstance(self.env_var_name, str):
            return [self.env_var_name]
        else:
            return []

    def argparse_argument_kwargs(self) -> Mapping[str, Any]:
        res = super().argparse_argument_kwargs()
        if self.default_value is None and self.collector.arg_required():
            res = {**res, "required": True}
        return {
            **res,
            **self.collector.argparse_argument_kwargs(),
            **self.arg_type.argparse_argument_kwargs(),
        }

    @staticmethod
    def store(
        arg_type: ArgType[T],
        *,
        default_value: Optional[str] = None,
        positional: Positional = Positional.FORBIDDEN,
        short_flag_name: Optional[str] = None,
        long_flag_name: ArgName = AutoArgName.DERIVED,
        config_key_name: ArgName = AutoArgName.DERIVED,
        env_var_name: ArgName = AutoArgName.FORBIDDEN,
    ) -> Arg[T]:
        """
        Creates an argument that stores the last provided value

        If a default value is provided, the argument can be omitted. However,
        if the default_value ``None`` is given (default), then
        the argument cannot be omitted.

        Args:
            argType: Parser that transforms a string into a value
            default_value: Default value
            positional: Whether this argument is present in positional arguments
            short_flag_name: Short option name (optional)
            long_flag_name: Long option name (auto. derived from fieldname by default)
            config_key_name: Config key name (auto. derived from fieldname by default)
            env_var_name: Environment variable name (forbidden by default)

        Returns:
            The constructed Arg instance
        """

        return Arg(
            arg_type=arg_type,
            collector=Collector.keep_last(),
            default_value=default_value,
            positional=positional,
            short_flag_name=short_flag_name,
            long_flag_name=long_flag_name,
            config_key_name=config_key_name,
            env_var_name=env_var_name,
        )

    @staticmethod
    def append(
        arg_type: ArgType[Sequence[W]],
        *,
        positional: Positional = Positional.FORBIDDEN,
        short_flag_name: Optional[str] = None,
        long_flag_name: ArgName = AutoArgName.DERIVED,
        config_key_name: ArgName = AutoArgName.DERIVED,
        env_var_name: ArgName = AutoArgName.FORBIDDEN,
    ) -> Arg[Sequence[W]]:
        """
        Creates an argument that stores the last provided value

        Args:
            argType: Parser that transforms a string into a value
            positional: Whether this argument is present in positional arguments
            short_flag_name: Short option name (optional)
            long_flag_name: Long option name (auto. derived from fieldname by default)
            config_key_name: Config key name (auto. derived from fieldname by default)
            env_var_name: Environment variable name (forbidden by default)

        Returns:
            The constructed Arg instance
        """
        return Arg(
            arg_type=arg_type,
            collector=Collector.append(),
            default_value=None,
            positional=positional,
            short_flag_name=short_flag_name,
            long_flag_name=long_flag_name,
            config_key_name=config_key_name,
            env_var_name=env_var_name,
        )
