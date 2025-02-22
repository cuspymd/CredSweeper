from typing import Tuple, Union

from credsweeper.common.constants import Severity
from credsweeper.credentials import Candidate
from credsweeper.credentials import LineData
from credsweeper.ml_model import MlValidator
import numpy as np
import pandas as pd

MlValidator()  # Initialize global MLValidator object


class CustomLineData(LineData):
    """Object that allows to create LineData from scanner results"""
    def __init__(self, line: str, value: str, line_num: int, path: str) -> None:
        self.line: str = line
        self.line_num: int = line_num
        self.path: str = path
        self.value = value


def get_candidates(line_data: dict):
    """Get list of candidates. 1 candidate for each rule that detected this line"""
    ld = CustomLineData(line_data["line"], line_data["value"], line_data["line_num"], line_data["path"])
    candidates = []
    for rule in line_data["RuleNames"]:
        candidates.append(Candidate([ld], [], rule, Severity.MEDIUM, [], True))

    return candidates


def get_features(line_data: Union[dict, pd.Series]):
    """Get features from a single detection using CredSweeper.MlValidator module"""
    value = line_data["value"]
    candidates = get_candidates(line_data)

    line_input = MlValidator.encode(value, MlValidator.char_to_index)

    common_features = MlValidator.extract_common_features(candidates)
    unique_features = MlValidator.extract_unique_features(candidates)

    extracted_features = np.hstack([common_features, unique_features])

    return line_input, extracted_features


def prepare_data(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Get features from a DataFrame detection using CredSweeper.MlValidator module"""
    X_values = []
    X_features = []

    for i, row in df.iterrows():
        line_input, extracted_features = get_features(row)
        X_values.append(line_input)
        X_features.append(extracted_features)

    X_values = np.array(X_values)
    X_features = np.array(X_features)

    return X_values, X_features
