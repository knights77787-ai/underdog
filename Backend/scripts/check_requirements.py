#!/usr/bin/env python3
"""
Backend에서 사용하는 import를 스캔해 requirements.txt와 비교합니다.
배포(Render 등) 전에 실행해 누락된 패키지가 없는지 확인하세요.

사용: Backend 폴더에서
  python scripts/check_requirements.py
"""
import re
from pathlib import Path

# Python 표준 라이브러리 (일부만; 전체는 importlib 등으로 확인 가능)
STDLIB = {
    "abc", "aifc", "argparse", "array", "ast", "asyncio", "base64", "binascii",
    "calendar", "cmath", "collections", "contextlib", "copy", "csv", "dataclasses",
    "datetime", "decimal", "difflib", "email", "encodings", "enum", "errno",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt", "getpass",
    "glob", "gzip", "hashlib", "heapq", "hmac", "html", "http", "imaplib",
    "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools",
    "json", "keyword", "lib2to3", "linecache", "locale", "logging", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "numbers",
    "operator", "optparse", "os", "pathlib", "pickle", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pydoc", "queue",
    "re", "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
    "secrets", "select", "selectors", "shelve", "shutil", "signal", "site",
    "smtplib", "socket", "socketserver", "sqlite3", "string", "stringprep",
    "struct", "subprocess", "sys", "sysconfig", "tabnanny", "tarfile", "telnetlib",
    "tempfile", "termios", "test", "textwrap", "threading", "time", "timeit",
    "tkinter", "token", "tokenize", "traceback", "tracemalloc", "tty", "turtledemo",
    "types", "typing", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xml",
    "xmlrpc", "zipapp", "zipfile", "zipimport", "_thread", "__future__",
}

# import 이름 -> PyPI 패키지 이름 (다른 경우만)
IMPORT_TO_PIP = {
    "whisper": "openai-whisper",
    "dotenv": "python-dotenv",
    "silero_vad": "silero-vad",
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
}

# 다른 패키지 의존성으로 보통 설치됨 (누락 경고 제외)
TRANSITIVE = {"pydantic"}  # fastapi 등이 가져옴


def top_level_module(name: str) -> str:
    """'foo.bar.baz' -> 'foo'"""
    return name.split(".")[0]


def find_imports_in_file(path: Path) -> set[str]:
    modules = set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return modules
    # import foo / import foo as x
    for m in re.finditer(r"^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)", text, re.MULTILINE):
        modules.add(top_level_module(m.group(1)))
    # from foo import ... / from foo.bar import ...
    for m in re.finditer(r"^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import", text, re.MULTILINE):
        modules.add(top_level_module(m.group(1)))
    return modules


def find_all_imports(backend_dir: Path) -> set[str]:
    collected = set()
    for py in backend_dir.rglob("*.py"):
        if ".venv" in str(py) or "scripts" in str(py) and py.name == "check_requirements.py":
            continue
        collected |= find_imports_in_file(py)
    return collected


def parse_requirements(req_path: Path) -> set[str]:
    """requirements.txt에서 패키지 이름만 추출 (버전 제거)."""
    in_requirements = set()
    if not req_path.is_file():
        return in_requirements
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip().split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        # package>=1.0, package[extra], package
        name = re.split(r"\[|>=|==|<=|>|<|~", line)[0].strip().lower()
        if name:
            in_requirements.add(name)
    return in_requirements


def main():
    backend_dir = Path(__file__).resolve().parent.parent
    req_path = backend_dir / "requirements.txt"

    used = find_all_imports(backend_dir)
    in_req = parse_requirements(req_path)

    # 로컬/표준 제외
    third_party = set()
    for u in used:
        if u in STDLIB or u in ("App", "app"):
            continue
        third_party.add(u)

    # PyPI 이름으로 변환
    need_pip_names = set()
    for t in third_party:
        need_pip_names.add(IMPORT_TO_PIP.get(t, t))

    # requirements에 없을 수 있는 이름 (일부는 의존성으로 들어옴)
    missing = []
    for p in need_pip_names:
        p_lower = p.lower()
        if p_lower in TRANSITIVE:
            continue
        if any(p_lower == r or p_lower in r or p_lower.replace("_", "-") == r for r in in_req):
            continue
        missing.append(p)

    if missing:
        print("다음 패키지가 requirements.txt에 없을 수 있습니다. 배포 전 확인하세요:")
        for m in sorted(missing):
            print(f"  - {m}")
        print("\n추가 예시:")
        for m in sorted(missing):
            print(f"  {m}>=...  # pip install {m} 로 버전 확인 후 추가")
    else:
        print("사용 중인 서드파티 import는 모두 requirements.txt에 반영된 것으로 보입니다.")


if __name__ == "__main__":
    main()
