// v3.0 Scenario-Based Assessment Data
// Dimensions: Anxiety, WTC, Learning Aptitude, STEAM/Humanities Tendency
const questions = [
    // ===== ANXIETY 영역 (8개) =====
    {
        id: 1,
        category: 'anxiety',
        subCategory: 'communication',
        situation: '영어 수업 시간, 선생님이 "오늘 배운 내용을 짝과 영어로 이야기해보세요"라고 말씀하십니다.',
        text: '이 순간 당신은 어떤 생각이 드나요?',
        textEn: 'The teacher says, "Discuss today\'s lesson with your partner in English." What goes through your mind?',
        options: { 5: '좋아, 재미있겠다!', 4: '할 수 있을 것 같아', 3: '음... 어떻게 시작하지?', 2: '뭐라고 말해야 할지 모르겠어', 1: '정말 하기 싫다, 피하고 싶어' },
        reverse: true, // Higher score = lower anxiety. Needs reversal.
        weight: 1.2
    },
    {
        id: 2,
        category: 'anxiety',
        subCategory: 'communication',
        situation: '영어로 발표 준비 중, 선생님이 "지금 준비한 것 일부만 먼저 발표해볼까요?"라고 하십니다.',
        text: '당신의 반응은?',
        textEn: 'While preparing an English presentation, the teacher asks, "Why not present a part of it now?" How do you react?',
        options: { 5: '네! 지금 보여드릴게요', 4: '조금 긴장되지만 할 수 있어요', 3: '심장이 빨리 뛰지만 해볼게요', 2: '머리가 하얘져서 생각이 안 나요', 1: '패닉 상태, 아무 말도 못하겠어요' },
        reverse: true,
        weight: 1.1
    },
    {
        id: 6,
        category: 'anxiety',
        subCategory: 'fear',
        situation: '영어로 발표했는데, 친구 몇 명이 웃었습니다. (이유 모름)',
        text: '당신은 어떻게 생각하나요?',
        textEn: 'After presenting in English, some classmates laugh. (Reason unknown) What do you think?',
        options: { 5: '별일 아니야, 다른 이유겠지', 4: '조금 신경 쓰이지만 넘어가요', 3: '내가 실수했나? 계속 생각나요', 2: '분명 내 영어가 이상해서 웃었을 거야', 1: '너무 창피해, 다시는 발표 못 해' },
        reverse: true,
        weight: 1.3
    },
    {
        id: 7,
        category: 'anxiety',
        subCategory: 'fear',
        situation: '선생님이 당신의 영어 문장을 칠판에 쓰시면서 "여기를 고쳐볼까요?"라고 하십니다.',
        text: '당신의 기분은?',
        textEn: 'The teacher writes your sentence on the board and says, "Shall we correct this?" How do you feel?',
        options: { 5: '좋아요, 배울 수 있는 기회네요', 4: '괜찮아요, 실수는 당연하니까', 3: '조금 부끄럽지만 참을 만해요', 2: '얼굴이 빨개지고 창피해요', 1: '모두가 나를 보고 있는 것 같아 견딜 수 없어요' },
        reverse: true,
        weight: 1.0
    },
    {
        id: 10,
        category: 'anxiety',
        subCategory: 'test',
        situation: '영어 말하기 시험 10분 전. 분명 연습했던 문장인데...',
        text: '당신의 상태는?',
        textEn: '10 minutes before an English speaking test. You practiced, but...',
        options: { 5: '연습한 대로만 하면 돼, 차분해요', 4: '약간 긴장되지만 기억나요', 3: '연습한 게 가물가물해요', 2: '머릿속이 백지가 된 것 같아요', 1: '아무것도 생각 안 나요, 포기 상태예요' },
        reverse: true,
        weight: 1.1
    },
    {
        id: 11,
        category: 'anxiety',
        subCategory: 'test',
        situation: '듣기 평가 중 한 단어를 놓쳤습니다.',
        text: '당신의 반응은?',
        textEn: 'You missed a word during a listening test. What\'s your reaction?',
        options: { 5: '괜찮아, 문맥으로 유추할 수 있어', 4: '아쉽지만 다음 문제에 집중하자', 3: '그 단어만 계속 생각나서 집중이 안돼', 2: '전체를 못 알아들은 것 같아 불안해', 1: '완전히 패닉, 나머지도 다 놓쳐버렸어' },
        reverse: true,
        weight: 1.0
    },
    {
        id: 13,
        category: 'anxiety',
        subCategory: 'confidence',
        situation: '영어 수업에서 답을 아는 질문에 선생님이 자원자를 찾고, 다른 친구들도 손을 듭니다.',
        text: '당신의 생각은?',
        textEn: 'You know the answer to a question in English class, and other students also raise their hands.',
        options: { 5: '나도 손을 든다. 내 답이 맞을거야', 4: '손을 든다. 틀려도 괜찮아', 3: '손을 들까 말까 망설인다', 2: '다른 친구들이 더 잘 알겠지', 1: '절대 손 안든다. 틀릴까봐 무섭다' },
        reverse: true,
        weight: 1.0
    },
    {
        id: 15,
        category: 'anxiety',
        subCategory: 'confidence',
        situation: '영어 실력이 늘지 않는 것 같은데, 친구가 "너 영어 많이 늘었다"고 칭찬해줍니다.',
        text: '당신의 반응은?',
        textEn: 'You feel your English isn\'t improving, but a friend compliments you. How do you react?',
        options: { 5: '고마워! 노력한 보람이 있네', 4: '정말? 그렇다니 다행이다', 3: '그냥 위로하는 말이겠지', 2: '아니야, 전혀 안 늘었어', 1: '나는 영어에 재능이 없나봐' },
        reverse: true,
        weight: 1.3
    },

    // ===== WTC (의사소통 의지) 영역 (8개) =====
    {
        id: 16,
        category: 'wtc',
        subCategory: 'classroom',
        situation: '선생님이 "오늘 배운 표현으로 자유롭게 문장을 만들어볼 사람?"이라고 물으십니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'The teacher asks, "Who wants to make a sentence using today\'s expressions?"',
        options: { 5: '바로 손을 들고 문장을 만들어봐요', 4: '생각을 정리하고 손을 들어요', 3: '하고 싶지만 망설여져요', 2: '다른 사람이 하기를 기다려요', 1: '절대 안 해요' },
        reverse: false,
        weight: 1.3
    },
    {
        id: 17,
        category: 'wtc',
        subCategory: 'classroom',
        situation: '그룹 활동에서 영어로 발표할 대표를 뽑습니다.',
        text: '당신의 선택은?',
        textEn: 'Your group needs a representative to present in English. What do you do?',
        options: { 5: '제가 할게요! 자원해요', 4: '뽑히면 할게요', 3: '다른 친구가 더 잘할 것 같아요', 2: '발표는 안 하고 싶어요', 1: '절대 안 해요, 다른 걸 하겠어요' },
        reverse: false,
        weight: 1.2
    },
    {
        id: 20,
        category: 'wtc',
        subCategory: 'social',
        situation: '길에서 길을 잃은 외국인 관광객을 만났습니다. 그들이 당신을 쳐다봅니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'You meet lost foreign tourists on the street. They look at you.',
        options: { 5: '먼저 다가가 "도와드릴까요?"라고 영어로 물어봐요', 4: '그들이 물으면 영어로 도와줘요', 3: '도와주고 싶지만 망설여져요', 2: '못 본 척하고 지나가요', 1: '피해서 가요' },
        reverse: false,
        weight: 1.1
    },
    {
        id: 21,
        category: 'wtc',
        subCategory: 'social',
        situation: '학교에 새로 온 외국인 학생이 혼자 앉아 있습니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'A new foreign student at school is sitting alone. What do you do?',
        options: { 5: '다가가서 영어로 말을 걸어요', 4: '친구와 함께 가서 말을 걸어요', 3: '말 걸고 싶지만 용기가 안 나요', 2: '눈인사만 해요', 1: '아무것도 안 해요' },
        reverse: false,
        weight: 1.0
    },
    {
        id: 23,
        category: 'wtc',
        subCategory: 'confidence',
        situation: '영어 캠프에서 "나의 꿈"을 주제로 즉흥 스피치 기회가 있습니다.',
        text: '당신의 선택은?',
        textEn: 'There\'s an impromptu speech opportunity on "My Dream" at English camp.',
        options: { 5: '도전해요! 완벽하지 않아도 괜찮아요', 4: '준비 시간을 조금 받고 해봐요', 3: '하고 싶지만 너무 떨려요', 2: '구경만 해요', 1: '절대 안 해요' },
        reverse: false,
        weight: 1.3
    },
    {
        id: 26,
        category: 'wtc',
        subCategory: 'motivation',
        situation: '주말에, 친구가 "영어로 영화 보면서 따라 말하기"를 제안합니다.',
        text: '당신의 반응은?',
        textEn: 'A friend suggests, "Want to watch a movie in English and repeat the lines?"',
        options: { 5: '좋아! 재미있겠다, 바로 해요', 4: '괜찮을 것 같아, 해봐요', 3: '별로 내키지 않지만 따라해요', 2: '그냥 한글 자막으로 보고 싶어', 1: '영어는 싫어, 다른 걸 하자' },
        reverse: false,
        weight: 1.2
    },
    {
        id: 29,
        category: 'wtc',
        subCategory: 'digital',
        situation: '좋아하는 해외 연예인이 SNS에 질문을 받고 있습니다. 영어로 댓글을 달면 답글을 받을 수도 있습니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'Your favorite foreign celebrity is taking questions on social media.',
        options: { 5: '영어로 질문이나 응원 댓글을 남겨요', 4: '번역기 도움을 받아서 써요', 3: '쓰고 싶지만 용기가 안 나요', 2: '다른 사람들 댓글에 \'좋아요\'만 눌러요', 1: '아무것도 안 해요' },
        reverse: false,
        weight: 0.9
    },
    {
        id: 30,
        category: 'wtc',
        subCategory: 'digital',
        situation: '온라인 게임에서 외국인 팀원을 만났습니다. 영어로 소통하면 더 재미있을 것 같습니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'You met foreign teammates in an online game.',
        options: { 5: '간단한 영어로라도 대화하며 게임을 이끌어요', 4: '게임 용어 정도는 영어로 말해요', 3: '채팅 대신 이모티콘이나 신호만 사용해요', 2: '채팅에 참여하지 않아요', 1: '소통이 불편해서 그냥 게임을 나와요' },
        reverse: false,
        weight: 0.9
    },

    // ===== APTITUDE (학습 능력) 영역 (7개) =====
    {
        id: 31,
        category: 'aptitude',
        subCategory: 'problem_solving',
        situation: '처음 보는 유형의 복잡한 수학 문제가 주어졌습니다.',
        text: '당신은 가장 먼저 무엇을 하나요?',
        textEn: 'You are given a complex math problem of a type you have never seen before.',
        options: { 5: '문제를 여러 작은 부분으로 나누어 분석한다', 4: '알고 있는 공식이나 비슷한 문제를 떠올려본다', 3: '일단 아는대로 시도해본다', 2: '해설이나 답을 먼저 찾아본다', 1: '어렵다고 생각하고 바로 도움을 요청한다' },
        reverse: false,
        weight: 1.2
    },
    {
        id: 32,
        category: 'aptitude',
        subCategory: 'curiosity',
        situation: '수업 시간에 배운 내용에 대해 "왜 그럴까?"하는 궁금증이 생겼습니다.',
        text: '당신은 어떻게 하나요?',
        textEn: 'A question "But why?" pops into your head about something you learned in class.',
        options: { 5: '수업이 끝나고 스스로 책이나 인터넷을 찾아본다', 4: '선생님께 바로 질문하거나 나중에 여쭤본다', 3: '친구들과 그 주제에 대해 이야기해본다', 2: '궁금하지만, 시험에 안 나오면 그냥 넘어간다', 1: '그런 궁금증이 별로 생긴 적이 없다' },
        reverse: false,
        weight: 1.1
    },
    {
        id: 33,
        category: 'aptitude',
        subCategory: 'resilience',
        situation: '열심히 공부한 시험에서 기대보다 낮은 점수를 받았습니다.',
        text: '시험지를 받은 후 당신의 생각은?',
        textEn: 'You got a lower score than expected on a test you studied hard for.',
        options: { 5: '어떤 문제를 왜 틀렸는지 분석하고 다음 계획을 세운다', 4: '아쉽지만, 다음엔 더 잘 볼 수 있을 거라고 생각한다', 3: '기분이 안 좋지만, 곧 잊어버리려고 노력한다', 2: '역시 나는 이 과목에 재능이 없다고 생각한다', 1: '공부한 것이 억울하고, 다시는 이 과목을 공부하기 싫어진다' },
        reverse: false,
        weight: 1.3
    },
    {
        id: 34,
        category: 'aptitude',
        subCategory: 'synthesis',
        situation: '학교 과제를 위해 여러 책과 인터넷 자료를 찾았습니다. 정보가 너무 많습니다.',
        text: '당신은 정보를 어떻게 처리하나요?',
        textEn: 'You have found too many books and web pages for a school assignment.',
        options: { 5: '핵심 내용만 요약하고 연결하여 새로운 생각을 정리한다', 4: '중요도 순으로 정리하고, 필요한 정보만 추려낸다', 3: '가장 마음에 드는 자료 하나를 중심으로 정리한다', 2: '자료들을 모두 복사-붙여넣기 해서 일단 제출한다', 1: '어디서부터 시작해야 할지 몰라 막막하다' },
        reverse: false,
        weight: 1.0
    },
    {
        id: 35,
        category: 'aptitude',
        subCategory: 'strategy',
        situation: '시험 공부를 할 때, 당신의 주된 학습 방식은?',
        text: '어떻게 공부하는 것을 가장 선호하나요?',
        textEn: 'When studying for a test, what is your primary method?',
        options: { 5: '전체적인 원리와 개념을 먼저 이해하려고 노력한다', 4: '중요하다고 강조된 부분을 집중적으로 공부한다', 3: '친구들과 예상 문제를 만들고 풀어본다', 2: '교과서나 요약본을 처음부터 끝까지 반복해서 읽는다', 1: '시험 전날에 벼락치기로 암기한다' },
        reverse: false,
        weight: 1.0
    },
    {
        id: 36,
        category: 'aptitude',
        subCategory: 'flexibility',
        situation: '내가 풀던 방식으로는 도저히 문제가 해결되지 않습니다.',
        text: '당신은 어떻게 대처하나요?',
        textEn: 'The problem can\'t be solved with your current method.',
        options: { 5: '즉시 다른 각도에서 접근하거나 새로운 방법을 시도한다', 4: '잠시 쉬고 나서 다른 방법을 생각해본다', 3: '내 방식이 맞을 것이라 믿고 계속 시도한다', 2: '다른 사람의 풀이 방법을 찾아본다', 1: '문제가 잘못됐다고 생각하거나 포기한다' },
        reverse: false,
        weight: 1.1
    },
    {
        id: 37,
        category: 'aptitude',
        subCategory: 'self_correction',
        situation: '과제를 제출하고 나서야 큰 실수를 한 것을 발견했습니다.',
        text: '당신의 반응은?',
        textEn: 'You found a big mistake only after submitting your assignment.',
        options: { 5: '실수를 분석하고 다음에는 반복하지 않도록 기록해둔다', 4: '선생님께 솔직하게 말씀드리고 수정할 기회를 요청한다', 3: '어쩔 수 없지. 다음부터 잘하자고 생각한다', 2: '아무도 모르게 넘어가기를 바란다', 1: '실수한 스스로를 자책하며 계속 신경쓴다' },
        reverse: false,
        weight: 1.0
    },

    // ===== TENDENCY (이과/문과 성향) 영역 (7개) =====
    {
        id: 38,
        category: 'tendency',
        subCategory: 'problem_type',
        situation: '자유 시간에 두 가지 활동 중 하나를 선택할 수 있습니다.',
        text: '어떤 활동을 더 선호하시나요?',
        textEn: 'You can choose one of two activities in your free time. Which do you prefer?',
        options: { 5: '규칙을 찾아 풀어내는 논리 퍼즐', 4: '전략을 세워 이기는 보드게임', 3: '친구들과 함께하는 스포츠', 2: '소설책을 읽거나 영화 감상하기', 1: '상상한 이야기를 그림이나 글로 표현하기' },
        reverse: false, // 5: 이과, 1: 문과
        weight: 1.2
    },
    {
        id: 39,
        category: 'tendency',
        subCategory: 'explanation_preference',
        situation: '새로운 개념에 대한 설명을 들어야 합니다.',
        text: '어떤 방식의 설명을 더 쉽게 이해하나요?',
        textEn: 'You need to listen to an explanation of a new concept.',
        options: { 5: '원인과 결과가 명확한 단계별 설명', 4: '도표와 데이터를 활용한 시각적 설명', 3: '실제 사례나 예시를 통한 설명', 2: '흥미로운 배경 스토리를 곁들인 설명', 1: '등장인물의 감정선을 따라가는 이야기 형식의 설명' },
        reverse: false,
        weight: 1.1
    },
    {
        id: 40,
        category: 'tendency',
        subCategory: 'hobby_preference',
        situation: '선물로 둘 중 하나의 키트를 받을 수 있습니다.',
        text: '어떤 것을 더 갖고 싶나요?',
        textEn: 'You can receive one of two kits as a gift.',
        options: { 5: '부품을 조립해서 움직이는 로봇 만들기 키트', 4: '화학 반응을 실험하는 과학 실험 키트', 3: '둘 다 비슷하게 흥미롭다', 2: '나만의 캐릭터를 만드는 미술용품 세트', 1: '짧은 소설을 써볼 수 있는 글쓰기 노트 세트' },
        reverse: false,
        weight: 1.3
    },
    {
        id: 41,
        category: 'tendency',
        subCategory: 'genre_preference',
        situation: '영화를 보러 갔습니다. 어떤 장르를 가장 먼저 확인하나요?',
        text: '가장 끌리는 영화 장르는 무엇인가요?',
        textEn: 'You went to see a movie. Which genre do you check first?',
        options: { 5: 'SF나 모든 사건이 논리적으로 해결되는 추리물', 4: '치밀한 계획으로 목표를 달성하는 첩보물', 3: '현실과 비슷한 코미디나 액션', 2: '주인공의 성장을 다룬 드라마', 1: '역사적 사건이나 인물의 삶을 다룬 영화' },
        reverse: false,
        weight: 1.0
    },
    {
        id: 42,
        category: 'tendency',
        subCategory: 'argument_style',
        situation: '토론을 보고 있습니다. 어떤 주장에 더 마음이 가나요?',
        text: '당신을 더 설득시키는 것은 무엇인가요?',
        textEn: 'You are watching a debate. Which argument is more persuasive to you?',
        options: { 5: '정확한 통계와 데이터를 근거로 한 주장', 4: '객관적인 사실과 논리적 순서에 따른 주장', 3: '상식적이고 합리적인 수준의 주장', 2: '많은 사람들이 공감하는 경험을 바탕으로 한 주장', 1: '듣는 사람의 마음을 움직이는 감동적인 이야기' },
        reverse: false,
        weight: 1.1
    },
    {
        id: 43,
        category: 'tendency',
        subCategory: 'decision_making',
        situation: '중요한 결정을 내려야 할 때, 주로 무엇에 의존하나요?',
        text: '당신의 결정 방식은?',
        textEn: 'When making an important decision, what do you mainly rely on?',
        options: { 5: '장점과 단점을 분석한 객관적인 표', 4: '가능한 모든 결과를 예측하고 최선의 수를 계산', 3: '과거의 경험과 현재 상황을 종합적으로 고려', 2: '내가 추구하는 가치나 신념에 부합하는지', 1: '마음이 끌리는 쪽, 소위 \'직감\'' },
        reverse: false,
        weight: 1.0
    },
    {
        id: 44,
        category: 'tendency',
        subCategory: 'project_style',
        situation: '자유 주제로 1년 동안 진행할 프로젝트를 선택해야 합니다.',
        text: '어떤 프로젝트에 더 흥미를 느끼나요?',
        textEn: 'You must choose a year-long project on a free topic.',
        options: { 5: '새로운 앱을 설계하거나 효율적인 시스템을 구축하는 프로젝트', 4: '특정 이론의 타당성을 데이터로 증명하는 연구 프로젝트', 3: '사회 문제를 해결하기 위한 캠페인 프로젝트', 2: '잊혀진 역사를 재조명하는 다큐멘터리 제작 프로젝트', 1: '세상의 다양한 사람들을 인터뷰하고 그들의 이야기를 엮는 프로젝트' },
        reverse: false,
        weight: 1.2
    },
];

const likertOptions = [
    { value: 5, label: '매우 그렇다' },
    { value: 4, label: '그렇다' },
    { value: 3, label: '보통이다' },
    { value: 2, label: '그렇지 않다' },
    { value: 1, label: '전혀 그렇지 않다' }
];

const gradeNorms = {
    default: {
        anxiety: { mean: 3.0, sd: 1.0 }, // 5점 만점 기준, 점수가 높을수록 불안이 '높음'
        wtc: { mean: 3.0, sd: 1.0 },
        aptitude: { mean: 3.0, sd: 1.0 },
        tendency: { mean: 3.0, sd: 1.0 } // 3점: 중립, >3: 이과, <3: 문과
    },
    '초3': { anxiety: { mean: 2.8, sd: 0.8 }, wtc: { mean: 3.5, sd: 0.7 }, aptitude: { mean: 3.7, sd: 0.8 }, tendency: { mean: 3.0, sd: 1.0 } },
    '초4': { anxiety: { mean: 2.9, sd: 0.8 }, wtc: { mean: 3.6, sd: 0.7 }, aptitude: { mean: 3.6, sd: 0.8 }, tendency: { mean: 3.0, sd: 1.0 } },
    '초5': { anxiety: { mean: 3.1, sd: 0.9 }, wtc: { mean: 3.4, sd: 0.8 }, aptitude: { mean: 3.5, sd: 0.9 }, tendency: { mean: 3.0, sd: 1.0 } },
    '초6': { anxiety: { mean: 3.2, sd: 0.9 }, wtc: { mean: 3.3, sd: 0.8 }, aptitude: { mean: 3.4, sd: 0.9 }, tendency: { mean: 3.0, sd: 1.0 } },
    '중1': { anxiety: { mean: 3.3, sd: 0.9 }, wtc: { mean: 3.2, sd: 0.8 }, aptitude: { mean: 3.3, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } },
    '중2': { anxiety: { mean: 3.4, sd: 1.0 }, wtc: { mean: 3.1, sd: 0.8 }, aptitude: { mean: 3.2, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } },
    '중3': { anxiety: { mean: 3.5, sd: 1.0 }, wtc: { mean: 3.0, sd: 0.9 }, aptitude: { mean: 3.1, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } },
    '고1': { anxiety: { mean: 3.4, sd: 1.0 }, wtc: { mean: 3.1, sd: 0.9 }, aptitude: { mean: 3.3, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } },
    '고2': { anxiety: { mean: 3.3, sd: 1.0 }, wtc: { mean: 3.2, sd: 0.9 }, aptitude: { mean: 3.4, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } },
    '고3': { anxiety: { mean: 3.2, sd: 1.0 }, wtc: { mean: 3.3, sd: 0.9 }, aptitude: { mean: 3.5, sd: 1.0 }, tendency: { mean: 3.0, sd: 1.0 } }
};

const subCategoryLabels = {
    anxiety_communication: '의사소통 불안',
    anxiety_fear: '평가 두려움',
    anxiety_test: '시험/수행 불안',
    anxiety_confidence: '자신감 결여',
    wtc_classroom: '수업 참여 의지',
    wtc_social: '사회적 소통 의지',
    wtc_digital: '디지털 소통 의지',
    wtc_confidence: '소통 자신감',
    wtc_motivation: '내재적 동기',
    aptitude_problem_solving: '문제해결력',
    aptitude_curiosity: '지적 호기심',
    aptitude_resilience: '학습 회복탄력성',
    aptitude_synthesis: '정보 통합력',
    aptitude_strategy: '학습 전략',
    aptitude_flexibility: '사고 유연성',
    aptitude_self_correction: '자기 교정',
    tendency_problem_type: '선호 문제 유형',
    tendency_explanation_preference: '선호 설명 방식',
    tendency_hobby_preference: '선호 취미',
    tendency_genre_preference: '선호 장르',
    tendency_argument_style: '선호 주장 방식',
    tendency_decision_making: '의사결정 방식',
    tendency_project_style: '선호 프로젝트',
};
