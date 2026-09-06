"""1. 수집 — google-play-scraper로 SNOW·B612 한국어 리뷰를 별점 층화 수집.

각 앱의 원본 리뷰를 data/raw/{name}_reviews.json,
원본 별점 분포를 data/raw/{name}_rating_dist.json으로 저장한다.

층화 비율(앱당 목표 ~250): 1점 40% / 2~3점 40% / 4~5점 20% (ADR-005).
견고성은 최소화한다 — 죽으면 재실행이 더 싸다 (ADR-007).
"""
import json
import time

from google_play_scraper import reviews, app, Sort

import config

# 별점별 목표 수집 건수 (합계 250 = 1점 40% / 2~3점 40% / 4~5점 20%)
SCORE_TARGETS = {1: 100, 2: 50, 3: 50, 4: 25, 5: 25}


def fetch_app_reviews(gp_id: str) -> tuple[list[dict], dict]:
    """별점별로 층화 수집한 리뷰 리스트와 원본 별점 분포(dict)를 반환.

    특정 별점이 목표보다 적게 반환돼도 정상 — 반환된 만큼만 담는다.
    """
    collected: list[dict] = []
    for score, target in SCORE_TARGETS.items():
        result, _ = reviews(
            gp_id,
            lang="ko",
            country="kr",
            sort=Sort.NEWEST,
            count=target,
            filter_score_with=score,
        )
        collected.extend(result)
        time.sleep(1)  # 차단 예방

    # 원본 별점 분포: app() 히스토그램 [1점, 2점, 3점, 4점, 5점]
    info = app(gp_id, lang="ko", country="kr")
    histogram = info.get("histogram") or []
    rating_dist = {str(i + 1): histogram[i] for i in range(len(histogram))}
    time.sleep(1)

    return collected, rating_dist


def main() -> None:
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)

    for app_def in config.APPS:
        name, gp_id = app_def["name"], app_def["gp_id"]
        collected, rating_dist = fetch_app_reviews(gp_id)

        reviews_path = config.DATA_RAW / f"{name}_reviews.json"
        dist_path = config.DATA_RAW / f"{name}_rating_dist.json"
        # datetime(at/repliedAt) 직렬화: default=str 없으면 TypeError로 저장 실패
        with open(reviews_path, "w", encoding="utf-8") as f:
            json.dump(collected, f, default=str, ensure_ascii=False)
        with open(dist_path, "w", encoding="utf-8") as f:
            json.dump(rating_dist, f, ensure_ascii=False)

        # 앱별 실제 수집 건수 + 층화된 별점 분포 출력
        by_score: dict[int, int] = {}
        for r in collected:
            by_score[r["score"]] = by_score.get(r["score"], 0) + 1
        sample_dist = {s: by_score.get(s, 0) for s in SCORE_TARGETS}
        print(f"[{name}] 수집 {len(collected)}건 | 표본 별점분포 {sample_dist} | 원본 분포 {rating_dist}")


if __name__ == "__main__":
    main()
