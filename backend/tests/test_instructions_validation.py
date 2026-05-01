"""Tests para _validate_instructions_length y persistencia de implementation_instructions."""
import asyncio
import os
import sys
import pytest
from dotenv import load_dotenv

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')

from routes.quote_actions import _validate_instructions_length
from fastapi import HTTPException


def test_empty_returns_none():
    assert _validate_instructions_length("") is None
    assert _validate_instructions_length(None) is None
    assert _validate_instructions_length("   ") is None


def test_short_html_passes():
    assert _validate_instructions_length("<p><b>Hola</b></p>") == "<p><b>Hola</b></p>"


def test_entities_counted_as_visible_chars():
    # "< > &" is 3 visible chars
    html = "<p>&lt;&gt;&amp;</p>"
    assert _validate_instructions_length(html) == html


def test_exceeds_limit_raises_422():
    long_text = "A" * 501
    html = f"<p>{long_text}</p>"
    with pytest.raises(HTTPException) as e:
        _validate_instructions_length(html, 500)
    assert e.value.status_code == 422
    assert "500" in e.value.detail


def test_html_tags_not_counted():
    # 100 'A's with heavy HTML should count as 100 (html tags excluded)
    html = "<p><b><i><u>" + ("A" * 100) + "</u></i></b></p>"
    assert _validate_instructions_length(html, 500) == html
