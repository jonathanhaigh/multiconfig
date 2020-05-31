#!/usr/bin/env python3

# Copyright 2020 Jonathan Haigh <jonathanhaigh@gmail.com>
# SPDX-License-Identifier: MIT

from multiconfig import multiconfig as mc

import argparse
import io
import json
import pathlib
import pytest
import sys
import tempfile
import unittest.mock as utm

TEST_FILE_PATH = pathlib.Path(__file__).resolve().parent / "testfile.txt"
with TEST_FILE_PATH.open() as f:
    TEST_FILE_CONTENT = f.read()

# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------


def split_str(s):
    return s.split()


# ------------------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------------------


class ArgparseError(RuntimeError):
    pass


class RaisingArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if status:
            raise ArgparseError(message)


# ------------------------------------------------------------------------------
# ConfigParser tests
# ------------------------------------------------------------------------------


def test_default_value_without_sources():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1")
    mc_parser.add_config("c2", default="v2")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": None, "c2": "v2"})
    assert values == expected_values


def test_default_value_from_config_default():
    mc_parser = mc.ConfigParser(config_default="v1")
    mc_parser.add_config("c1")
    mc_parser.add_config("c2", default="v2")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1", "c2": "v2"})
    assert values == expected_values


def test_suppress():
    mc_parser = mc.ConfigParser(config_default=mc.SUPPRESS)
    mc_parser.add_config("c1")
    mc_parser.add_config("c2", default="v2")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c2": "v2"})
    assert values == expected_values


def test_required_config_not_found():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2")
    with pytest.raises(mc.RequiredConfigNotFoundError):
        mc_parser.parse_config()


def test_required_config_found():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2")
    mc_parser.add_source(mc.DictSource, {"c1": "v1"})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1", "c2": None})
    assert values == expected_values


def test_partially_parse_config():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2")
    mc_parser.add_source(mc.DictSource, {"c2": "v2"})
    values = mc_parser.partially_parse_config()
    expected_values = mc._namespace_from_dict({"c1": None, "c2": "v2"})
    assert values == expected_values


def test_types():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", type=str)
    mc_parser.add_config("c2", type=int)
    mc_parser.add_config("c3", type=pathlib.Path)
    mc_parser.add_config("c4", type=json.loads)
    mc_parser.add_config("c5", type=split_str)
    mc_parser.add_source(
        mc.DictSource,
        {
            "c1": "v1",
            "c2": "10",
            "c3": "/some/path",
            "c4": '{ "a": "va", "b": 10, "c": [ 1, 2, 3 ] }',
            "c5": "word1 word2 word3",
        },
    )
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {
            "c1": "v1",
            "c2": 10,
            "c3": pathlib.Path("/some/path"),
            "c4": {"a": "va", "b": 10, "c": [1, 2, 3]},
            "c5": ["word1", "word2", "word3"],
        }
    )
    assert values == expected_values
    assert isinstance(values.c1, str)
    assert isinstance(values.c2, int)
    assert isinstance(values.c3, pathlib.Path)
    assert isinstance(values.c4, dict)
    assert isinstance(values.c5, list)


def test_file_opening():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", type=mc.FileType("r"))
    mc_parser.add_config("c2", type=mc.FileType("w"))
    with tempfile.TemporaryDirectory() as tmpdir:
        mc_parser.add_source(
            mc.DictSource,
            {"c1": str(TEST_FILE_PATH), "c2": f"{tmpdir}/testfile2.txt"},
        )
        values = mc_parser.parse_config()
        assert values.c1.read() == TEST_FILE_CONTENT
        values.c2.write(TEST_FILE_CONTENT)


def test_validate_name():
    mc_parser = mc.ConfigParser()
    with pytest.raises(ValueError):
        mc_parser.add_config("--c1")


def test_validate_type():
    mc_parser = mc.ConfigParser()
    with pytest.raises(TypeError):
        mc_parser.add_config("c1", type=1)


def test_valid_str_choice():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", choices=["a", "b"])
    mc_parser.add_source(mc.DictSource, {"c1": "a"})
    expected_values = mc._namespace_from_dict({"c1": "a"})
    values = mc_parser.parse_config()
    assert values == expected_values


def test_valid_int_choice():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", type=int, choices=[1, 2])
    mc_parser.add_source(mc.DictSource, {"c1": "2"})
    expected_values = mc._namespace_from_dict({"c1": 2})
    values = mc_parser.parse_config()
    assert values == expected_values


def test_invalid_str_choice():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", choices=["a", "b"])
    with pytest.raises(mc.InvalidChoiceError):
        mc_parser.add_source(mc.DictSource, {"c1": "c"})
        mc_parser.parse_config()


def test_invalid_int_choice():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", type=int, choices=[1, 2])
    with pytest.raises(mc.InvalidChoiceError):
        mc_parser.add_source(mc.DictSource, {"c1": "3"})
        mc_parser.parse_config()


def test_store_const():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_const", const="v1")
    mc_parser.add_source(mc.DictSource, {"c1": True})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_store_const_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_const", const="v1")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": None})
    assert values == expected_values


def test_store_const_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config(
        "c1", action="store_const", const="v1a", default="v1b"
    )
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1b"})
    assert values == expected_values


def test_store_true():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true")
    mc_parser.add_source(mc.DictSource, {"c1": "v1"})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": True})
    assert values == expected_values


def test_store_true_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": False})
    assert values == expected_values


def test_store_true_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true", default="v1")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_store_false():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false")
    mc_parser.add_source(mc.DictSource, {"c1": "v1"})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": False})
    assert values == expected_values


def test_store_false_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": True})
    assert values == expected_values


def test_store_false_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false", default="v1")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_append():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append")
    mc_parser.add_source(mc.DictSource, {"c1": "v1"})
    mc_parser.add_source(mc.DictSource, {"c1": "v2"})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": ["v1", "v2"]})
    assert values == expected_values


def test_append_with_choices():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", type=int, choices=[0, 1])
    mc_parser.add_source(mc.DictSource, {"c1": 0})
    mc_parser.add_source(mc.DictSource, {"c1": 1})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": [0, 1]})
    assert values == expected_values


def test_append_with_invalid_choice():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", choices=[0, 1])
    mc_parser.add_source(mc.DictSource, {"c1": 0})
    mc_parser.add_source(mc.DictSource, {"c1": 2})
    with pytest.raises(mc.InvalidChoiceError):
        mc_parser.parse_config()


def test_append_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", type=int, default=[0])
    mc_parser.add_source(mc.DictSource, {"c1": 1})
    mc_parser.add_source(mc.DictSource, {"c1": 2})
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": [0, 1, 2]})
    assert values == expected_values


def test_append_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": None})
    assert values == expected_values


def test_append_required_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", required=True)
    with pytest.raises(mc.RequiredConfigNotFoundError):
        mc_parser.parse_config()


def test_append_required_missing_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", required=True, default=["v0"])
    with pytest.raises(mc.RequiredConfigNotFoundError):
        mc_parser.parse_config()


def test_append_missing_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", type=int, default=[0])
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": [0]})
    assert values == expected_values


# ------------------------------------------------------------------------------
# SimpleArgparseSource tests
# ------------------------------------------------------------------------------


def test_simple_argparse_source():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1 v1 --c2 v2a".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2a", "c3": None, "c4": "v4"}
    )
    assert values == expected_values


def test_simple_argparse_source_with_missing_required_config():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1")
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3", required=True)
    mc_parser.add_config("c4", default="v4")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1 v1 --c2 v2a".split()):
        with pytest.raises(mc.RequiredConfigNotFoundError):
            mc_parser.parse_config()


def test_simple_argparse_source_with_suppress():
    mc_parser = mc.ConfigParser(config_default=mc.SUPPRESS)
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1 v1 --c2 v2a".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2a", "c4": "v4"}
    )
    assert values == expected_values


def test_simple_argparse_source_with_config_added_after_source():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_source(mc.SimpleArgparseSource)
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    with utm.patch.object(sys, "argv", "prog --c1 v1 --c3 v3".split()):
        with pytest.raises(SystemExit):
            values = mc_parser.parse_config()
    with utm.patch.object(sys, "argv", "prog --c1 v1".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2", "c3": None, "c4": "v4"}
    )
    assert values == expected_values


def test_simple_argparse_source_with_prog():
    mc_parser = mc.ConfigParser()
    mc_parser.add_source(
        mc.SimpleArgparseSource,
        argument_parser_class=RaisingArgumentParser,
        prog="PROG_TEST",
    )
    with utm.patch.object(sys, "argv", "prog --c1 v1".split()):
        with pytest.raises(ArgparseError, match="PROG_TEST"):
            mc_parser.parse_config()


def test_simple_argparse_source_with_store_const():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_const", const="v1")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_simple_argparse_source_with_store_const_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_const", const="v1")
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": None})
    assert values == expected_values


def test_simple_argparse_source_with_store_const_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config(
        "c1", action="store_const", const="v1a", default="v1b"
    )
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1b"})
    assert values == expected_values


def test_simple_argparse_source_with_store_true():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": True})
    assert values == expected_values


def test_simple_argparse_source_with_store_true_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true")
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": False})
    assert values == expected_values


def test_simple_argparse_source_with_store_true_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_true", default="v1")
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_simple_argparse_source_with_store_false():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": False})
    assert values == expected_values


def test_simple_argparse_source_with_store_false_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false")
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": True})
    assert values == expected_values


def test_simple_argparse_source_with_store_false_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="store_false", default="v1")
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": "v1"})
    assert values == expected_values


def test_simple_argparse_source_with_append():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1 v1 --c1 v2".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": ["v1", "v2"]})
    assert values == expected_values


def test_simple_argparse_source_with_append_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", type=int, default=[0])
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog --c1 1 --c1 2".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": [0, 1, 2]})
    assert values == expected_values


def test_simple_argparse_source_with_append_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append")
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": None})
    assert values == expected_values


def test_simple_argparse_source_with_append_required_missing():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", required=True)
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog".split()):
        with pytest.raises(mc.RequiredConfigNotFoundError):
            mc_parser.parse_config()


def test_simple_argparse_source_with_append_required_missing_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", required=True, default=["v0"])
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog".split()):
        with pytest.raises(mc.RequiredConfigNotFoundError):
            mc_parser.parse_config()


def test_simple_argparse_source_with_append_missing_with_default():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", action="append", type=int, default=[0])
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(sys, "argv", "prog".split()):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict({"c1": [0]})
    assert values == expected_values


# ------------------------------------------------------------------------------
# JsonSource tests
# ------------------------------------------------------------------------------


def test_json_source():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    fileobj = io.StringIO(
        """{
        "c1": "v1",
        "c2": "v2a"
    }"""
    )
    mc_parser.add_source(mc.JsonSource, fileobj=fileobj)
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2a", "c3": None, "c4": "v4"}
    )
    assert values == expected_values


def test_json_source_with_missing_required_config():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1")
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3", required=True)
    mc_parser.add_config("c4", default="v4")
    fileobj = io.StringIO(
        """{
        "c1": "v1",
        "c2": "v2a"
    }"""
    )
    mc_parser.add_source(mc.JsonSource, fileobj=fileobj)
    with pytest.raises(mc.RequiredConfigNotFoundError):
        mc_parser.parse_config()


def test_json_source_with_suppress():
    mc_parser = mc.ConfigParser(config_default=mc.SUPPRESS)
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    fileobj = io.StringIO(
        """{
        "c1": "v1",
        "c2": "v2a"
    }"""
    )
    mc_parser.add_source(mc.JsonSource, fileobj=fileobj)
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2a", "c4": "v4"}
    )
    assert values == expected_values


def test_json_source_with_config_added_after_source():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", required=True)
    mc_parser.add_config("c2", default="v2")
    fileobj = io.StringIO(
        """{
        "c1": "v1",
        "c3": "v3"
    }"""
    )
    mc_parser.add_source(mc.JsonSource, fileobj=fileobj)
    mc_parser.add_config("c3")
    mc_parser.add_config("c4", default="v4")
    values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {"c1": "v1", "c2": "v2", "c3": None, "c4": "v4"}
    )
    assert values == expected_values


# ------------------------------------------------------------------------------
# Multiple source tests
# ------------------------------------------------------------------------------


def test_multiple_sources():
    mc_parser = mc.ConfigParser()
    mc_parser.add_config("c1", type=int, choices=[1, 2], required=True)
    mc_parser.add_config("c2", type=str, default="v2")
    mc_parser.add_config("c3", type=pathlib.Path)
    mc_parser.add_config("c4", type=split_str, default="word1 word2".split())
    mc_parser.add_config("c5", choices=["v5", "v5a"], required=True)
    mc_parser.add_config("c6", default="v6")
    mc_parser.add_config("c7", type=json.loads)
    mc_parser.add_config("c8", default="v8")
    mc_parser.add_config("c9", action="append", type=int, default=[0, 1])
    fileobj = io.StringIO(
        """{
        "c1": 1,
        "c2": "v2a",
        "c9": 2
    }"""
    )
    mc_parser.add_source(mc.JsonSource, fileobj=fileobj)
    mc_parser.add_source(mc.DictSource, {"c9": 3})
    mc_parser.add_source(mc.SimpleArgparseSource)
    with utm.patch.object(
        sys, "argv", "prog --c5 v5 --c7 [1,2] --c9 4".split()
    ):
        values = mc_parser.parse_config()
    expected_values = mc._namespace_from_dict(
        {
            "c1": 1,
            "c2": "v2a",
            "c3": None,
            "c4": "word1 word2".split(),
            "c5": "v5",
            "c6": "v6",
            "c7": [1, 2],
            "c8": "v8",
            "c9": [0, 1, 2, 3, 4],
        }
    )
    assert values == expected_values


# ------------------------------------------------------------------------------
# Free function tests
# ------------------------------------------------------------------------------


def test_getattr_or_none():
    obj = mc.Namespace()
    setattr(obj, "c1", "v1")
    setattr(obj, "c2", None)
    setattr(obj, "c3", mc.NONE)
    assert mc._getattr_or_none(obj, "c1") == "v1"
    assert mc._getattr_or_none(obj, "c2") is None
    assert mc._getattr_or_none(obj, "c3") is mc.NONE
    assert mc._getattr_or_none(obj, "c4") is mc.NONE


def test_has_nonnone_attr():
    obj = mc.Namespace()
    setattr(obj, "c1", "v1")
    setattr(obj, "c2", None)
    setattr(obj, "c3", mc.NONE)
    assert mc._has_nonnone_attr(obj, "c1")
    assert mc._has_nonnone_attr(obj, "c2")
    assert not mc._has_nonnone_attr(obj, "c3")
    assert not mc._has_nonnone_attr(obj, "c4")
