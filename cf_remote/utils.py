import hashlib
import os
import shutil
import sys
import re
import json
import getpass
from collections import OrderedDict
from cf_remote import log
from datetime import datetime


def is_in_past(date):
    now = datetime.now()
    date = datetime.strptime(date, "%Y-%m-%d")
    return now > date


def cache(func):
    """Memoization decorator similar to functools.cache (Python 3.9+)"""
    memo = {}

    def wrapper(*args, **kwargs):
        kwargs = OrderedDict(sorted(kwargs.items()))
        key = str({"args": args, "kwargs": kwargs})
        if key not in memo:
            memo[key] = func(*args, **kwargs)
        return memo[key]

    return wrapper


def canonify(string):
    legal = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    string = string.strip()
    string = string.lower()
    string = string.replace(".", "_")
    string = string.replace(" ", "_")
    results = []
    for c in string:
        if c in legal:
            results.append(c)
    return "".join(results)


def user_error(msg):
    sys.exit("%s: " % os.path.basename(sys.argv[0]) + msg)


def exit_success():
    sys.exit(0)


def mkdir(path):
    if not os.path.exists(path):
        log.info("Creating directory: '{}'".format(path))
        os.makedirs(path)
    else:
        log.debug("Directory already exists: '{}'".format(path))


def ls(path):
    return os.listdir(path)


def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return None


def save_file(path, data):
    try:
        if "/" in path:
            mkdir("/".join(path.split("/")[0:-1]))
        with open(path, "w") as f:
            f.write(data)
    except PermissionError:
        user_error("No permission to write to '{}'.".format(path))


def pretty(data):
    return json.dumps(data, indent=2)


def is_package_url(string):
    return bool(re.match(r"https?://.+/.+\.(rpm|deb|msi|tar\.gz|tgz)", string))


def get_package_name(url):
    assert is_package_url(url)
    return url.rsplit("/", 1)[-1]


def parse_json(text):
    return json.loads(text, object_pairs_hook=OrderedDict)


def read_json(path):
    try:
        with open(path, "r") as f:
            return parse_json(f.read())
    except FileNotFoundError:
        return None


def write_json(path, data):
    data = pretty(data)
    return save_file(path, data)


def os_release(inp):
    if not inp:
        log.debug("Cannot parse os-release file (empty)")
        return None
    d = OrderedDict()
    for line in inp.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, sep, value = line.partition("=")
        assert "=" not in key
        if len(value) > 1 and value[0] == value[-1] and value[0] in ["'", '"']:
            value = value[1:-1]
        d[key] = value
    return d


def parse_version(string):
    if not string:
        return None
    # 'CFEngine Core 3.12.1 \n CFEngine Enterprise 3.12.1'
    #                ^ split and use this part for version number
    words = string.split()
    if len(words) < 3:
        return None
    version_number = words[2]
    edition = words[1]
    if edition == "Core":
        edition = "Community"
    if "Enterprise" in string:
        edition = "Enterprise"
    return "{} ({})".format(version_number, edition)


def parse_systeminfo(data):
    # TODO: This is not great, it misses a lot of the nested data
    lines = [s.strip() for s in data.split("\n") if s.strip()]
    data = OrderedDict()
    for line in lines:
        sections = line.split(":")
        key = sections[0].strip()
        value = ":".join(sections[1:]).strip()
        data[key] = value
    return data


def column_print(data):
    width = 0
    for key in data:
        if len(key) > width:
            width = len(key)

    for key, value in data.items():
        fill = " " * (width - len(key))
        print("{}{} : {}".format(key, fill, value))


def is_file_string(string):
    return string and string.startswith(("./", "~/", "/", "../"))


def expand_list_from_file(string):
    assert is_file_string(string)

    location = os.path.expanduser(string)
    if not os.path.exists(location):
        user_error("Hosts file '{}' does not exist".format(location))
    if not os.path.isfile(location):
        user_error("'{}' is not a file".format(location))
    if not os.access(location, os.R_OK):
        user_error("Cannot read '{}' - Permission denied".format(location))

    with open(location, "r") as f:
        hosts = [line.strip() for line in f if line.strip()]

    return hosts


def strip_user(host):
    """Strips the 'user@' info from a host spec"""
    idx = host.find("@")
    if idx != -1:
        return host[(idx + 1) :]
    return host


def whoami():
    return getpass.getuser()


def print_progress_dot(*args):
    print(".", end="")
    sys.stdout.flush()  # STDOUT is line-buffered


def copy_file(input_path, output_path):
    filename = os.path.basename(input_path)
    output_dir = os.path.dirname(output_path)

    tmp_filename = ".{}.tmp".format(filename)
    tmp_output_path = os.path.join(output_dir, tmp_filename)

    shutil.copyfile(input_path, tmp_output_path)
    os.rename(tmp_output_path, output_path)


def is_different_checksum(checksum, content):
    assert type(content) == bytes

    digest = hashlib.sha256(content).digest().hex()
    return checksum != digest
