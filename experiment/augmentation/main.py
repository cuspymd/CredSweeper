import os
from shutil import rmtree
from multiprocessing import Pool
import pandas as pd
import random
import sys
from pathlib import Path
import tqdm

from obfuscation import get_obfuscated_value, generate_value, SecretCreds

BASE_PATH = ["test", "src", "other"]
COLUMN_TYPES = {
    "Id": str,
    "FileID": str,
    "Domain": str,
    "RepoName": str,
    "FilePath": str,
    "LineStart:LineEnd": str,
    "GroundTruth": str,
    "WithWords": str,
    "InURL": str,
    "InRuntimeParameter": str,
    "CharacterSet": str,
    "CryptographyKey": str,
    "PredefinedPattern": str,
    "VariableNameType": str,
    "Entropy": float,
    "Base64Encode": str,
    "HexEncode": str,
    "URLEncode": str,
    "Category": str
}
RENAME_OLD_COLUMNS = {
    "LineStart:LineEnd": "Old_LineStart:LineEnd",
    "FilePath": "Old_FilePath"
}
RENAME_NEW_COLUMNS = {
    "New_LineNumb": "LineStart:LineEnd",
    "New_FilePath": "FilePath"
}


def get_pool_count() -> int:
    """Get the number of pools based on doubled CPUs in the system"""
    return os.cpu_count() * 2


def load_meta(meta_path, directory):
    meta_file = directory + ".csv"
    meta_path = meta_path / meta_file
    df = pd.read_csv(meta_path, dtype=COLUMN_TYPES)
    return df


def obfuscate_row(row, meta, secret_creds):
    category = meta.Category
    try:
        position = int(meta.ValueStart)
        pos_end = int(meta.ValueEnd)
    except ValueError:
        return row
    space_len = len(row) - len(row.lstrip())
    value = row[position + space_len:pos_end + space_len]
    if category == "Predefined Pattern":
        pattern = meta.PredefinedPattern
        obfuscated_value = get_obfuscated_value(value, pattern)
    else:
        if meta.WithWords == "1" and meta.Category not in ["Authentication Key & Token", "Generic Secret",
                                                           "Generic Token"]:
            obfuscated_value = secret_creds.get_word_secret()
        elif meta.Category == "Password":
            obfuscated_value = secret_creds.get_password()
        else:
            obfuscated_value = generate_value(value)

    if position > 0:
        obfuscated_line = row[:position + space_len] + obfuscated_value + row[position + space_len + len(value):]
    elif position == -1:
        obfuscated_line = row.replace(value, obfuscated_value)
    else:
        obfuscated_line = obfuscated_value + row[position + space_len + len(value):]

    return obfuscated_line


def add_raw_lines(meta_df, filepath, content):
    secret_creds = SecretCreds()
    temp_df = meta_df[meta_df.FilePath == filepath]
    false_df = temp_df[temp_df.GroundTruth == "F"]
    # Get line for row with "false" label
    for index, row in false_df.iterrows():
        line_numb = int(row["LineStart:LineEnd"].split(":")[0])
        meta_df.loc[index, "RawLine"] = content[line_numb - 1]
    # Get line for row with "true" label
    true_df = temp_df[temp_df.GroundTruth == "T"]
    for index, row in true_df.iterrows():
        line_numb = row["LineStart:LineEnd"].split(":")
        line = ""
        for l_n in range(int(line_numb[0]), int(line_numb[0]) + 1):
            obf_row = obfuscate_row(content[l_n - 1], row, secret_creds)
            line += obf_row
        meta_df.loc[index, "RawLine"] = line
    # Get line for row with "Template" label(temporary solution)
    template_df = temp_df[temp_df.GroundTruth == "Template"]
    for index, row in template_df.iterrows():
        line_numb = row["LineStart:LineEnd"].split(":")
        line = ""
        for l_n in range(int(line_numb[0]), int(line_numb[0]) + 1):
            obf_row = obfuscate_row(content[l_n - 1], row, secret_creds)
            line += obf_row
        meta_df.loc[index, "RawLine"] = line


def write2aug_file(repo_local_path, meta_df, aug_file):
    fls_path = list(set(meta_df.FilePath))
    for filepath in fls_path:
        with open(repo_local_path / filepath, "r") as reader:
            content = reader.readlines()
        add_raw_lines(meta_df, filepath, content)
    with open(repo_local_path / aug_file, "w") as writer:
        Rows = meta_df.RawLine
        writer.writelines(Rows)


def write_meta_file(meta_df, meta_file):
    save_df = meta_df[meta_df.GroundTruth != "F"]
    save_df.to_csv(meta_file)


def join_series(series):
    meta_df = pd.DataFrame(series)
    return meta_df


def write_meta(aug_df, aug_metapath):
    aug_df = pd.concat(aug_df)
    aug_df = aug_df[aug_df["GroundTruth"] != "F"]
    aug_df["GroundTruth"] = "T"
    aug_df.rename(columns=RENAME_OLD_COLUMNS, inplace=True)
    aug_df.rename(columns=RENAME_NEW_COLUMNS, inplace=True)
    aug_df.to_csv(aug_metapath)


def get_linage(repo_local_path, df):
    fls_path = list(set(df["FilePath"]))
    files_length = {}
    overall_linage = 0
    for filepath in fls_path:
        with open(repo_local_path / filepath, "r") as reader:
            content = reader.readlines()
        overall_linage += len(content)
        files_length[filepath] = len(content)
    return files_length, overall_linage


def get_extentions(meta_df):
    file_paths = set(meta_df["FilePath"])
    exts = set()
    for file_path in file_paths:
        if "." in file_path:
            exts.update(["." + file_path.split(".")[-1]])
    return list(exts)


def get_true_row(df, idx, aug_file):
    temp_df = df[df["GroundTruth"] != "F"]
    fl_path = list(temp_df["FilePath"])
    if len(fl_path) == 0:
        return None, idx

    lines = list(temp_df["LineStart:LineEnd"])
    rand = random.randint(0, len(fl_path) - 1)
    line_numb = lines[rand].split(":")
    t_df = temp_df.iloc[rand].copy()
    line_diff = int(line_numb[1]) - int(line_numb[0])
    new_linenumb = str(idx) + ":" + str(idx + line_diff)
    add_series = pd.Series({
        "New_LineNumb": new_linenumb,
        "New_FilePath": aug_file,
        "RawLine": ""
    })
    idx += line_diff
    t_df = t_df.append(add_series)
    return t_df, idx


def get_false_row(row_numb, aug_filename, files_length, fl_true_lines):
    fl_path = list(files_length.keys())

    rand = random.randint(0, len(fl_path) - 1)
    fl_name = fl_path[rand]
    fl_length = files_length[fl_name]
    # Filter true lines
    true_lines = fl_true_lines[fl_name]
    if fl_length == len(true_lines):
        return None

    t_df = None
    while t_df is None:
        rand_row = random.randint(1, fl_length)
        if rand_row in true_lines:
            continue
        orig_linenumb = str(rand_row) + ":" + str(rand_row)
        new_linenumb = str(row_numb) + ":" + str(row_numb)
        t_df = pd.Series({
            "FilePath": fl_name,
            "LineStart:LineEnd": orig_linenumb,
            "GroundTruth": "F",
            "New_LineNumb": new_linenumb,
            "New_FilePath": aug_filename,
            "RawLine": ""
        })
    return t_df


def get_true_lines(df):
    fl_paths = list(set(df["FilePath"]))
    true_df = df[df["GroundTruth"] != "F"]
    fls_true_lines = {}
    true_cred_count = 0
    for fl_name in fl_paths:
        fl_lines = []
        temp_df = true_df[true_df["FilePath"] == fl_name]
        lines = list(temp_df["LineStart:LineEnd"])
        true_cred_count += len(lines)
        for line in lines:
            ls = line.split(":")
            if ls[0] == ls[1]:
                fl_lines.append(int(ls[0]))
            else:
                fl_lines.extend([l for l in range(int(ls[0]), int(ls[1]) + 1)])
        fls_true_lines[fl_name] = fl_lines
    return fls_true_lines, true_cred_count


def generate_rows(repo_local_path, aug_filename, df, true_stake, scale):
    files_length, overall_linage = get_linage(repo_local_path, df)
    new_series = []
    aug_file_linage = int(scale * overall_linage)
    fl_true_lines, true_cred_count = get_true_lines(df)
    aug_file_linage = int(true_cred_count * scale / true_stake)
    for row_numb in range(1, aug_file_linage):
        rand = random.uniform(0, 1)
        if rand < true_stake:
            ground_trues, idx = get_true_row(df, row_numb, aug_filename)
            row_numb = idx
        else:
            ground_trues = get_false_row(row_numb, aug_filename, files_length, fl_true_lines)
        if ground_trues is None:
            row_numb -= 1
            continue
        new_series.append(ground_trues)
    return new_series


def aug_dir(arg):
    repo_local_path, meta_path, dir_name, true_stake, scale = arg

    meta_data = load_meta(meta_path, dir_name)
    aug_meta = str(repo_local_path / "aug_data" / "meta" / dir_name) + ".csv"
    new_meta = []
    for base in BASE_PATH:
        aug_filetemp = repo_local_path / "aug_data" / "data" / dir_name / base
        os.makedirs(aug_filetemp)
        aug_filetemp = aug_filetemp / dir_name
        meta_df = meta_data[meta_data["FilePath"].str.contains(base)]
        augument_list = ["Password", "Generic Secret", "Predefined Pattern", "Seed, Salt, Nonce", "Generic Token", "Authentication Key & Token"]
        meta_df = meta_df[meta_df["Category"].isin(augument_list)]
        exts = get_extentions(meta_df)
        for extension in exts:
            bool_series = meta_df["FilePath"].str.endswith(extension)
            ext_df = meta_df[bool_series]
            aug_filename = str(aug_filetemp) + extension
            new_series = generate_rows(repo_local_path, aug_filename, ext_df, true_stake, scale)
            if new_series:
                new_meta_df = join_series(new_series)
                write2aug_file(repo_local_path, new_meta_df, aug_filename)
                new_meta.append(new_meta_df)
    if new_meta:
        write_meta(new_meta, aug_meta)


def build_corpus(repo_local_path, meta_path, repos_paths, true_stake: float, scale: float):
    """ Build the corpus for this repo.

        Parameters
        ----------
        repo_path: str
            Path to the CredPosDataset repository
        meta_path: str
            Path to the metadata
        repos_paths: List[str]
            List of repos directory names
        true_stake:
            Part of the rows with "True" cases in the aggregated data

        Returns
        -------
        list
            A list of strings (i.e., the extracts)
        """
    try:
        rmtree(repo_local_path / "aug_data")
    except OSError:
        pass
    os.makedirs(repo_local_path / "aug_data")
    os.makedirs(repo_local_path / "aug_data" / "meta")
    print(
        f"Start augmentation for {len(repos_paths)} repos, Generated data will be saved to {repo_local_path / 'aug_data'}")
    args = []
    for rep_name in repos_paths:
        args.append((repo_local_path, meta_path, rep_name, true_stake, scale))

    with Pool(processes=get_pool_count()) as p:
        max_ = len(repos_paths)
        with tqdm.tqdm(total=max_) as pbar:
            for i, _ in enumerate(p.imap_unordered(aug_dir, args)):
                pbar.update()
    print(f"Augmentation finished")


if __name__ == "__main__":
    CredDataDirectory = sys.argv[1]
    true_stake = sys.argv[2]
    scale = sys.argv[3]

    try:
        CredDataDirectory = os.path.abspath(CredDataDirectory)
    except:
        raise ValueError("Please set a valid CredData directory")
    if not os.path.isdir(CredDataDirectory):
        raise ValueError("Please set a valid CredData. It should be a valid path")

    try:
        true_stake = float(true_stake)
    except:
        raise ValueError("Please set a valid true_stake. It cannot contain commas, spaces, or characters.")
    if true_stake < 0 or true_stake > 0.5:
        raise ValueError("Please set a valid true_stake. It should be between 0 and 0.5")

    try:
        scale = float(scale)
    except:
        raise ValueError("Please set a valid scale. It cannot contain commas, spaces, or characters.")

    repo_path = Path(CredDataDirectory)
    data_path = repo_path / "data"
    meta_path = repo_path / "meta"
    repos_paths = os.listdir(data_path)

    build_corpus(repo_path, meta_path, repos_paths, true_stake, scale)
