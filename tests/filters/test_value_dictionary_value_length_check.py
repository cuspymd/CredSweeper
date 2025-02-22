import pytest

from credsweeper.filters import ValueDictionaryValueLengthCheck
from tests.test_utils.dummy_line_data import get_line_data


class TestValueDictionaryValueLengthCheck:
    def test_value_dictionary_value_length_check_p(self, file_path: pytest.fixture,
                                                   success_line: pytest.fixture) -> None:
        line_data = get_line_data(file_path, line=success_line, pattern=r"(?P<value>.*$)")
        assert ValueDictionaryValueLengthCheck().run(line_data) is False

    @pytest.mark.parametrize("line", ["Cra", "CrackleCrackleCrackleCrackleCrackleCrackle123"])
    def test_value_dictionary_value_length_check_n(self, file_path: pytest.fixture, line: str) -> None:
        line_data = get_line_data(file_path, line=line, pattern=r"(?P<value>.*$)")
        assert ValueDictionaryValueLengthCheck().run(line_data) is True

    def test_value_dictionary_value_length_check_none_value_n(self, file_path: pytest.fixture,
                                                              success_line: pytest.fixture) -> None:
        line_data = get_line_data(file_path, line=success_line)
        assert ValueDictionaryValueLengthCheck().run(line_data) is True
