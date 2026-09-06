"""공통 설정 — 경로 상수, 대상 앱, API 키 로드.

이후 모든 파이프라인 단계(collect/preprocess/tag/analyze)가 import 한다.
"""
from pathlib import Path

from dotenv import load_dotenv
import os

# 경로 상수 (이 파일: ROOT/src/config.py → ROOT는 두 단계 상위)
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
TAXONOMY_PATH = ROOT / "taxonomy.json"
DOCS = ROOT / "docs"

# 대상 앱 (둘 다 SNOW Corporation, 구글플레이) — 검증된 패키지명
APPS = [
    {"name": "snow", "gp_id": "com.campmobile.snow"},
    {"name": "b612", "gp_id": "com.linecorp.b612.android"},
]


def load_api_key() -> str | None:
    """.env의 ANTHROPIC_API_KEY를 읽어 반환. 없으면 None."""
    load_dotenv(ROOT / ".env")
    return os.getenv("ANTHROPIC_API_KEY")
