#!/usr/bin/env python3

# Copyright 2020 Jonathan Haigh <jonathanhaigh@gmail.com>
# SPDX-License-Identifier: MIT

import argparse
import copy
import json
import operator
import re

# Make argparse.FileType available in this module
FileType = argparse.FileType


# ------------------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------------------


class ParseError(RuntimeError):
    """
    Base class for exceptions indicating a configuration error.
    """


class RequiredConfigNotFoundError(ParseError):
    """
    Exception raised when a required config value could not be found from any
    source.
    """


class InvalidChoiceError(ParseError):
    """
    Exception raised when a config value is not from a specified set of values.
    """

    def __init__(self, spec, value):
        super().__init__(
            f"invalid choice '{value}' for config item '{spec.name}'; "
            f"valid choices are {spec.choices}"
        )


# ------------------------------------------------------------------------------
# Tags
# ------------------------------------------------------------------------------


class _SuppressAttributeCreation:
    def __str__(self):
        return "==SUPPRESS=="


SUPPRESS = _SuppressAttributeCreation()


class _None:
    def __str__(self):
        return "==NONE=="


NONE = _None()

# ------------------------------------------------------------------------------
# Classes
# ------------------------------------------------------------------------------


class Namespace:
    def __str__(self):
        return str(vars(self))

    def __eq__(self, other):
        return other.__class__ == self.__class__ and vars(other) == vars(self)

    __repr__ = __str__


class ArgparseSource:
    def __init__(self, config_specs):
        self._config_specs = config_specs
        self._parsed_values = None

    def add_configs_to_argparse_parser(self, argparse_parser):
        for spec in self._config_specs:
            argparse_parser.add_argument(
                self._config_name_to_arg_name(spec.name),
                action=spec.action,
                nargs=spec.nargs,
                const=spec.const,
                default=NONE,
                type=str,
                help=spec.help,
                **spec.source_specific_options(self.__class__),
            )

    def notify_parsed_args(self, argparse_namespace):
        self._parsed_values = namespace(argparse_namespace, self._config_specs)

    def parse_config(self):
        return self._parsed_values

    @staticmethod
    def _config_name_to_arg_name(config_name):
        return f"--{config_name.replace('_', '-')}"


class SimpleArgparseSource(ArgparseSource):
    """
    Obtains config values from the command line using argparse.ArgumentParser.

    This class is simpler to use than ArgparseSource but does not allow adding
    arguments beside those added to the ConfigParser.

    Do not create objects of this class directly - create them via
    ConfigParser.add_source() instead:
    config_parser.add_source(multiconfig.SimpleArgparseSource, **options)

    Extra options that can be passed to ConfigParser.add_source() for
    SimpleArgparseSource are:
    * argument_parser_class: a class derived from argparse.ArgumentParser to
      use instead of ArgumentParser itself. This can be useful if you want to
      override ArgumentParser's exit() or error() methods.

    * Extra arguments to pass to ArgumentParser.__init__() (or the __init__()
      method for the class specified by the 'argument_parser_class' option.
      E.g.  'prog', 'allow_help'. You probably don't want to use the
      'argument_default' option though - see ConfigParser.__init__()'s
      'config_default' option instead.
    """

    def __init__(
        self,
        config_specs,
        argument_parser_class=argparse.ArgumentParser,
        **kwargs,
    ):
        super().__init__(config_specs)
        self._argparse_parser = argument_parser_class(**kwargs)
        super().add_configs_to_argparse_parser(self._argparse_parser)

    def parse_config(self):
        super().notify_parsed_args(self._argparse_parser.parse_args())
        return super().parse_config()


class JsonSource:
    """
    Obtains config values from a JSON file.

    Do not create objects of this class directly - create them via
    ConfigParser.add_source() instead:
    config_parser.add_source(multiconfig.JsonSource, **options)

    Extra options that can be passed to ConfigParser.add_source() for
    JsonSource are:
    * path: path to the JSON file to parse.
    * fileobj: a file object representing a stream of JSON data.

    Note: exactly one of the 'path' and 'fileobj' options must be given.
    """

    def __init__(self, config_specs, path=None, fileobj=None):
        self._config_specs = config_specs
        self._path = path
        self._fileobj = fileobj

        if path and fileobj:
            raise ValueError(
                "JsonSource's 'path' and 'fileobj' options were both "
                "specified but only one is expected"
            )

    def parse_config(self):
        json_values = self._get_json()
        values = Namespace()
        for spec in self._config_specs:
            if spec.name in json_values:
                setattr(values, spec.name, json_values[spec.name])
        return namespace(values, self._config_specs)

    def _get_json(self):
        if self._path:
            with open(self._path, mode="r") as f:
                return json.load(f)
        else:
            return json.load(self._fileobj)


class ConfigSpec:
    def __init__(
        self,
        name,
        action="store",
        nargs=None,
        const=None,
        default=NONE,
        type=str,
        choices=None,
        required=False,
        help=None,
        source_specific_options=None,
    ):
        self._name = name
        self._validate_name(name)

        self._action = action
        self._validate_action(action)

        self._nargs = nargs
        self._validate_nargs(nargs)

        self._const = const
        self._validate_const(const)

        self._default = default

        self._type = type
        self._validate_type(type)

        self._choices = choices
        self._required = required
        self._help = help
        self._source_specific_options = source_specific_options or {}

    name = property(operator.attrgetter("_name"))
    action = property(operator.attrgetter("_action"))
    nargs = property(operator.attrgetter("_nargs"))
    const = property(operator.attrgetter("_const"))
    default = property(operator.attrgetter("_default"))
    type = property(operator.attrgetter("_type"))
    choices = property(operator.attrgetter("_choices"))
    required = property(operator.attrgetter("_required"))
    help = property(operator.attrgetter("_help"))

    @staticmethod
    def _validate_name(name):
        if re.match(r"[^0-9A-Za-z_]", name) or re.match(r"^[^a-zA-Z_]", name):
            raise ValueError(
                f"Invalid config name '{name}', "
                "must be a valid Python identifier"
            )

    @staticmethod
    def _validate_action(action):
        if action in (
            "store_const",
            "store_true",
            "store_false",
            "append",
            "append_const",
            "count",
            "extend",
        ):
            raise NotImplementedError(
                f"action '{action}' has not been implemented"
            )
        if action != "store":
            raise ValueError(f"unknown action '{action}'")

    @staticmethod
    def _validate_nargs(nargs):
        if nargs is not None:
            raise NotImplementedError(
                "'nargs' argument has not been implemented"
            )

    @staticmethod
    def _validate_const(const):
        if const is not None:
            raise NotImplementedError(
                "'const' argument has not been implemented"
            )

    @staticmethod
    def _validate_type(type):
        if not callable(type):
            raise TypeError("'type' argument must be callable")

    def source_specific_options(self, source_class):
        opts = {}
        for candidate in self._source_specific_options:
            if issubclass(candidate, source_class):
                opts.update(self._source_specific_options[candidate])
        return opts


class ConfigParser:
    def __init__(self, config_default=NONE):
        self._config_specs = []
        self._sources = []
        self._parsed_values = Namespace()
        self._config_default = config_default

    def add_config(self, name, **kwargs):
        extra_kwargs = {}
        if "default" not in kwargs:
            extra_kwargs["default"] = self._config_default
        spec = ConfigSpec(name, **kwargs, **extra_kwargs)
        self._config_specs.append(spec)
        return spec

    def add_source(self, source_class, **kwargs):
        source = source_class(copy.copy(self._config_specs), **kwargs)
        self._sources.append(source)
        return source

    def add_preparsed_values(self, preparsed_values):
        for spec in self._config_specs:
            value = getattr_or_none(preparsed_values, spec.name)
            if value is not NONE:
                value = spec.type(value)
                if spec.choices and value not in spec.choices:
                    raise InvalidChoiceError(spec, value)
                setattr(self._parsed_values, spec.name, value)

    def partially_parse_config(self):
        for source in self._sources:
            new_values = source.parse_config()
            self.add_preparsed_values(new_values)
        return self._get_configs_with_defaults()

    def parse_config(self):
        values = self.partially_parse_config()
        self._check_required_configs()
        return values

    def _get_configs_with_defaults(self):
        values = copy.copy(self._parsed_values)
        for spec in self._config_specs:
            if not has_nonnone_attr(values, spec.name):
                if spec.default is NONE:
                    setattr(values, spec.name, None)
                elif spec.default is not SUPPRESS:
                    setattr(values, spec.name, spec.default)
        return values

    def _check_required_configs(self):
        for spec in self._config_specs:
            if not has_nonnone_attr(self._parsed_values, spec.name):
                if spec.required:
                    raise RequiredConfigNotFoundError(
                        f"Did not find value for config item '{spec.name}'"
                    )


# ------------------------------------------------------------------------------
# Free functions
# ------------------------------------------------------------------------------


def getattr_or_none(obj, attr):
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return NONE


def has_nonnone_attr(obj, attr):
    return getattr_or_none(obj, attr) is not NONE


def namespace(obj, config_specs):
    ns = Namespace()
    for spec in config_specs:
        if has_nonnone_attr(obj, spec.name):
            setattr(ns, spec.name, getattr(obj, spec.name))
    return ns
