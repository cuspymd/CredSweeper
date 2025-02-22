from typing import List

import pytest

from .common import BaseTestRule


class TestSlackToken(BaseTestRule):
    @pytest.fixture(params=[["https://hooks.slack.com/services/T_GIREOGI/B_FLYING_/Slack1webhook2teststring"]])
    def lines(self, request) -> List[str]:
        return request.param

    @pytest.fixture
    def rule_name(self) -> str:
        return "Slack Webhook"
