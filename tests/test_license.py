"""Tests for Lathe license validation."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lathe.license import (
    LICENSE_ENV_VAR,
    LICENSE_FILE,
    _read_license_env,
    _read_license_file,
    _validate_key,
    is_licensed,
)


class TestValidateKey:
    def test_valid_key(self):
        assert _validate_key("SL-ABCD-1234") is True

    def test_valid_key_minimal(self):
        assert _validate_key("SL-ABCD") is True

    def test_none_returns_false(self):
        assert _validate_key(None) is False

    def test_empty_string_returns_false(self):
        assert _validate_key("") is False

    def test_wrong_prefix_returns_false(self):
        assert _validate_key("XX-ABCD-1234") is False

    def test_too_short_returns_false(self):
        assert _validate_key("SL-AB") is False

    def test_non_string_returns_false(self):
        assert _validate_key(12345) is False


class TestReadLicenseEnv:
    def test_env_var_present(self):
        with patch.dict(os.environ, {LICENSE_ENV_VAR: "SL-ENV-KEY1"}):
            assert _read_license_env() == "SL-ENV-KEY1"

    def test_env_var_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _read_license_env() is None

    def test_env_var_empty(self):
        with patch.dict(os.environ, {LICENSE_ENV_VAR: ""}):
            assert _read_license_env() is None


class TestReadLicenseFile:
    def test_valid_license_file(self, tmp_path):
        license_file = tmp_path / "license.json"
        license_file.write_text(json.dumps({
            "key": "SL-FILE-1234",
            "product": "lathe-mcp",
            "email": "test@example.com",
            "issued": "2026-01-01",
        }))
        with patch("lathe.license.LICENSE_FILE", license_file):
            assert _read_license_file() == "SL-FILE-1234"

    def test_missing_file(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with patch("lathe.license.LICENSE_FILE", missing):
            assert _read_license_file() is None

    def test_malformed_json(self, tmp_path):
        bad_file = tmp_path / "license.json"
        bad_file.write_text("this is not json {{{")
        with patch("lathe.license.LICENSE_FILE", bad_file):
            assert _read_license_file() is None

    def test_json_without_key_field(self, tmp_path):
        no_key = tmp_path / "license.json"
        no_key.write_text(json.dumps({"product": "lathe-mcp"}))
        with patch("lathe.license.LICENSE_FILE", no_key):
            assert _read_license_file() is None

    def test_json_array_instead_of_object(self, tmp_path):
        arr_file = tmp_path / "license.json"
        arr_file.write_text(json.dumps(["not", "a", "dict"]))
        with patch("lathe.license.LICENSE_FILE", arr_file):
            assert _read_license_file() is None


class TestIsLicensed:
    def test_no_license_returns_false(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with patch.dict(os.environ, {}, clear=True):
            with patch("lathe.license.LICENSE_FILE", missing):
                assert is_licensed() is False

    def test_valid_env_var_returns_true(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with patch.dict(os.environ, {LICENSE_ENV_VAR: "SL-TEST-0000"}, clear=True):
            with patch("lathe.license.LICENSE_FILE", missing):
                assert is_licensed() is True

    def test_valid_file_returns_true(self, tmp_path):
        license_file = tmp_path / "license.json"
        license_file.write_text(json.dumps({"key": "SL-FILE-9999"}))
        with patch.dict(os.environ, {}, clear=True):
            with patch("lathe.license.LICENSE_FILE", license_file):
                assert is_licensed() is True

    def test_env_var_takes_precedence_over_file(self, tmp_path):
        license_file = tmp_path / "license.json"
        license_file.write_text(json.dumps({"key": "SL-FILE-9999"}))
        with patch.dict(os.environ, {LICENSE_ENV_VAR: "SL-ENV-1111"}, clear=True):
            with patch("lathe.license.LICENSE_FILE", license_file):
                assert is_licensed() is True

    def test_invalid_env_var_falls_back_to_file(self, tmp_path):
        license_file = tmp_path / "license.json"
        license_file.write_text(json.dumps({"key": "SL-FILE-9999"}))
        with patch.dict(os.environ, {LICENSE_ENV_VAR: "INVALID"}, clear=True):
            with patch("lathe.license.LICENSE_FILE", license_file):
                assert is_licensed() is True
