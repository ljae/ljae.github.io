---
name: review-ranking
description: Ego Lite 후기 조사·기존 재채점·시행착오 회귀 검증·수집 전략 학습을 한 회차 실행한다.
---

# 후기 랭킹 개선 회차

1. `docs/REVIEW_RANKING_AGENTS.md`와 ego-browser 스킬을 읽는다.
2. `run.py --agents plan --limit 6`과 `run.py --agents replay`를 읽는다.
   `ranking-research`에게 계획의 관련 시행착오·지점·표본 부족을 검토하게 한다.
3. 작업 전체에 하나의 Ego Lite TaskSpace만 만들고 그 숫자 ID를 저장한다.
   `run.py --agents run --space-id <ID> --limit 6`으로 실제 수집부터 재채점까지 실행한다.
   한 회차 최대 12질의다. 브라우저 오류나 사용자 제어 상태에서 재시도하지 않는다.
4. `ranking-learning-verifier`에게 테스트·영수증·학습 횟수·순위 근거를 독립 확인하게 한다.
   오류가 나면 원인과 다음 조치를 보고한다. 정답 픽스처나 가중치를 바꿔 통과시키지 않는다.
5. 성공한 브라우저 작업은 같은 TaskSpace에서 `finish({keep: []})`를 한 번 호출한다.
   결과는 실제 수집 수·검증 후 신규 근거 수·중복/탈락 수·학습 여부로 보고한다.
   사용자 요청 범위의 로컬 데이터 갱신을 완료하며 배포 여부는 별도로 명시한다.
6. 운영 배포가 요청되면 `--agents bundle`의 공개 후보 배치를 커밋·푸시하고,
   `collect.yml`을 `rescore_only=true`로 실행한다. 최신 운영 캐시에서 게이트와
   학습을 완료한 데이터 커밋 및 이어지는 Pages 배포까지 `/verify-landed`로
   확인한다. 오래된 로컬 캐시의 산출물을 최신 운영 자료 위에 덮지 않는다.
