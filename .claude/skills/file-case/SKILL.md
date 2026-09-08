---
name: file-case
description: 대화·메일로 받은 신고('OO학원이 국어 랭킹에 있는데 영어학원이다', '이 후기는 남의 얘기다')를 사례 대장(pipeline/wiki/cases)에 파일로 적고 바로 진단으로 넘긴다. 사용자가 학원·후기 오류를 말로 알려 줄 때 쓴다.
---

# 신고를 사례로 적기

웹 접수가 아니라 **말로 받은 신고**를 대장에 넣는다. 적지 않으면 그 신고는
대화가 끝나는 순간 사라지고, 같은 신고가 다시 왔을 때 '같은 것인지 새 것인지'
가릴 수 없다 — 그것이 진짜 비용이다.

## 절차

1. **학원을 찾는다.** 등록명·별칭·영문 약칭을 여러 표기로:
   ```bash
   jq -r '.[] | select(.displayName|test("<이름 일부>")) | [.id,.displayName,.regionId,(.subjects|join(","))] | @tsv' app/assets/data/academies.json
   jq -r '.[] | select(.displayName|test("<이름 일부>")) | [.id,.displayName,.regionId] | @tsv' app/assets/data/registry.json
   ```
   둘 다 없으면 `pipeline/.cache/neis_raw.json` 을 본다(동 경계·분야 필터로
   빠졌을 수 있다). 그래도 없으면 사례의 `entity_key` 를 `unknown` 으로 두고
   `## 진단` 에 그 사실을 적는다 — 없는 것도 신고다.

2. **적는다.** 신고 문장은 **그대로** 옮긴다(요약하지 않는다 — 명사를 고르는
   것은 case-triage 의 일이다).
   ```bash
   cd pipeline && ../.venv/bin/python -c "from edutree import cases; print(cases.new_manual('<id>', '<표시명>', '''<신고 문장 그대로>''', reason='<other_academy|not_review|ad|outdated|not_true|fix|other>'))"
   ```
   근거 글 한 건에 대한 신고면 `url_hash=` 를 함께 준다(학원 페이지의
   `auto:posts` 링크가 그 해시다).

3. **바로 진단으로.** 만들어진 경로로 `case-triage` 를 부른다. 그다음은
   `/triage-reports` 4단계부터와 같다.

교재(textbook) 신고도 같은 명령이다 — `entity_type='textbook'` 을 준다.
