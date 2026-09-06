"""2. 전처리 + 층화 샘플 확정 — data/raw/*.json → data/processed/sample.csv.

google-play-scraper 원본을 표준 스키마로 정규화하고, 중복·빈 리뷰를 제거하며,
PII(userName 등)를 드롭한다. 별점 층화는 collect가 이미 수행했으므로 여기서는
앱당 목표(~250)를 넘을 때만 별점 비율을 유지하며 보정한다(재수집 아님, ADR-007).
"""
import json

import pandas as pd

import config

# ARCHITECTURE.md 스키마 컬럼 순서 (태깅 컬럼은 tag step 담당)
SCHEMA_COLS = ["review_id", "app", "store", "lang", "rating", "date", "app_version", "content"]

# 앱당 목표 표본 (전체 ~500). collect가 이미 이 규모로 층화 수집함.
PER_APP_TARGET = 250


def load_raw() -> pd.DataFrame:
    """data/raw의 앱별 리뷰 JSON을 읽어 app 컬럼을 붙여 하나로 합친다."""
    frames = []
    for app_def in config.APPS:
        name = app_def["name"]
        with open(config.DATA_RAW / f"{name}_reviews.json", encoding="utf-8") as f:
            rows = json.load(f)
        df = pd.DataFrame(rows)
        df["app"] = name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """스키마 정규화 + 중복·빈 리뷰 제거 + PII 드롭 + date를 YYYY-MM로."""
    out = pd.DataFrame(
        {
            "review_id": df["reviewId"],
            "app": df["app"],
            "store": "google",
            "lang": "ko",
            "rating": df["score"],
            "date": pd.to_datetime(df["at"]).dt.strftime("%Y-%m"),
            "app_version": df["reviewCreatedVersion"],  # 결측 허용
            "content": df["content"].str.strip(),
        }
    )
    # userName 등 원본의 다른 필드는 위에서 명시적으로 취하지 않아 자연 드롭됨(PII).
    out = out[out["content"].str.len() > 0]           # 빈/공백 리뷰 제거
    out = out.dropna(subset=["review_id"])
    out = out.drop_duplicates(subset=["review_id"])   # 조인 키 유일성
    return out[SCHEMA_COLS].reset_index(drop=True)


def build_sample(df: pd.DataFrame) -> pd.DataFrame:
    """앱당 ~250(전체 ~500)로 확정. 목표 초과 시에만 별점 비율을 유지하며 샘플."""
    parts = []
    for name, g in df.groupby("app", sort=False):
        if len(g) > PER_APP_TARGET:
            frac = PER_APP_TARGET / len(g)
            g = g.groupby("rating", group_keys=False).apply(
                lambda x: x.sample(frac=frac, random_state=0)
            )
        parts.append(g)
    return pd.concat(parts).reset_index(drop=True)


def main() -> None:
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    sample = build_sample(clean(load_raw()))
    out_path = config.DATA_PROCESSED / "sample.csv"
    sample.to_csv(out_path, index=False, encoding="utf-8")

    dist = sample.groupby("app")["rating"].value_counts().unstack(fill_value=0).sort_index(axis=1)
    print(f"[preprocess] 샘플 {len(sample)}건 → {out_path}")
    print(f"앱별 건수: {sample['app'].value_counts().to_dict()}")
    print("앱×별점 분포:")
    print(dist)


if __name__ == "__main__":
    main()
