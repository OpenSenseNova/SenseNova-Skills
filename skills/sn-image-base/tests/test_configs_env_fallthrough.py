"""Regression tests for issue #165: empty-string env vars must not clobber
the built-in defaults (option C in the issue: a set non-empty value wins, an
empty one falls through to the next env name or the class default).

Every SN_* config env var is scrubbed from the environment first, so the
results only depend on what each test sets.
"""

from __future__ import annotations

import pytest
from sn_image_base.configs import Configs, Field

SN_ENV_VARS = [
    "SN_API_KEY",
    "SN_BASE_URL",
    "SN_IMAGE_GEN_API_KEY",
    "SN_IMAGE_GEN_BASE_URL",
    "SN_IMAGE_GEN_MODEL_TYPE",
    "SN_IMAGE_GEN_MODEL",
    "SN_CHAT_API_KEY",
    "SN_CHAT_BASE_URL",
    "SN_CHAT_MODEL",
    "SN_CHAT_TYPE",
    "SN_TEXT_API_KEY",
    "SN_TEXT_BASE_URL",
    "SN_TEXT_MODEL",
    "SN_TEXT_TYPE",
    "SN_VISION_API_KEY",
    "SN_VISION_BASE_URL",
    "SN_VISION_MODEL",
    "SN_VISION_TYPE",
]


@pytest.fixture(autouse=True)
def scrub_sn_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every SN_* config env var, so each test starts from a clean slate."""
    for var in SN_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_empty_sn_image_gen_model_resolves_built_in_default(monkeypatch) -> None:
    # ``.env.example`` ships ``SN_IMAGE_GEN_MODEL=`` (empty). A verbatim copy
    # of that file must not clobber the built-in default model.
    monkeypatch.setenv("SN_IMAGE_GEN_MODEL", "")
    assert Configs().SN_IMAGE_GEN_MODEL == "sensenova-u1.5-lite"


def test_non_empty_sn_image_gen_model_wins(monkeypatch) -> None:
    monkeypatch.setenv("SN_IMAGE_GEN_MODEL", "sensenova-u1.5-pro")
    assert Configs().SN_IMAGE_GEN_MODEL == "sensenova-u1.5-pro"


def test_empty_specific_var_falls_through_to_next_env_name(monkeypatch) -> None:
    # ``SN_IMAGE_GEN_API_KEY=""`` must fall through to ``SN_API_KEY``.
    monkeypatch.setenv("SN_IMAGE_GEN_API_KEY", "")
    monkeypatch.setenv("SN_API_KEY", "dummy-value-from-shared-var")
    assert Configs().SN_IMAGE_GEN_API_KEY == "dummy-value-from-shared-var"


def test_all_env_names_empty_keeps_class_default(monkeypatch) -> None:
    # When every env name of a field is set-but-empty, the class default stays.
    monkeypatch.setenv("SN_IMAGE_GEN_BASE_URL", "")
    monkeypatch.setenv("SN_BASE_URL", "")
    assert Configs().SN_IMAGE_GEN_BASE_URL == "https://token.sensenova.cn/v1"


def test_empty_env_with_int_target_is_skipped_not_converted(monkeypatch) -> None:
    # An empty value must be skipped before type conversion: ``int("")``
    # raises ValueError today; the fix must not attempt the conversion.
    field = Field("SOME_TEST_INT")
    monkeypatch.setenv("SOME_TEST_INT", "")
    assert field.resolve(int) is None


def test_non_empty_env_with_int_target_is_converted(monkeypatch) -> None:
    field = Field("SOME_TEST_INT")
    monkeypatch.setenv("SOME_TEST_INT", "30")
    assert field.resolve(int) == 30
