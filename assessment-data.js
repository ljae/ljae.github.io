// 질문 데이터
const questions = [
  // ===== ANXIETY 영역 (15개) =====
  // Communication Apprehension (의사소통 불안) - 5문항
  {
    id: 1,
    category: 'anxiety',
    subCategory: 'communication',
    text: '영어로 말할 때 내가 한 말이 맞는지 확신이 서지 않는다.',
    textEn: 'I never feel quite sure of myself when speaking in English.',
    reverse: false,
    weight: 1.2
  },
  {
    id: 2,
    category: 'anxiety',
    subCategory: 'communication',
    text: '수업 중 갑자기 영어로 대답해야 할 때 당황한다.',
    textEn: 'I start to panic when I have to speak without preparation.',
    reverse: false,
    weight: 1.1
  },
  {
    id: 3,
    category: 'anxiety',
    subCategory: 'communication',
    text: '다른 학생들 앞에서 영어로 말하는 것이 부끄럽다.',
    textEn: 'I feel self-conscious about speaking English in front of others.',
    reverse: false,
    weight: 1.0
  },
  {
    id: 4,
    category: 'anxiety',
    subCategory: 'communication',
    text: '영어로 말할 때 머릿속이 하얗게 변한다.',
    textEn: 'My mind goes blank when speaking English.',
    reverse: false,
    weight: 1.1
  },
  {
    id: 5,
    category: 'anxiety',
    subCategory: 'communication',
    text: '영어 발음이 이상할까 봐 걱정된다.',
    textEn: 'I worry about my pronunciation sounding strange.',
    reverse: false,
    weight: 0.9
  },
  // Fear of Negative Evaluation (부정적 평가 두려움) - 4문항
  {
    id: 6,
    category: 'anxiety',
    subCategory: 'fear',
    text: '다른 학생들이 내 영어 실력을 비웃을까 봐 걱정된다.',
    textEn: 'I am afraid other students will laugh at my English.',
    reverse: false,
    weight: 1.3
  },
  {
    id: 7,
    category: 'anxiety',
    subCategory: 'fear',
    text: '선생님이 내 실수를 지적할 때마다 긴장된다.',
    textEn: 'I get nervous when the teacher corrects my mistakes.',
    reverse: false,
    weight: 1.0
  },
  {
    id: 8,
    category: 'anxiety',
    subCategory: 'fear',
    text: '친구들이 나를 영어 못하는 사람으로 볼까 봐 두렵다.',
    textEn: 'I fear being perceived as bad at English.',
    reverse: false,
    weight: 1.2
  },
  {
    id: 9,
    category: 'anxiety',
    subCategory: 'fear',
    text: '실수했을 때 다른 사람들이 어떻게 생각할지 신경 쓰인다.',
    textEn: 'I worry about what others think when I make mistakes.',
    reverse: false,
    weight: 1.1
  },
  // Test Anxiety (시험/과제 불안) - 3문항
  {
    id: 10,
    category: 'anxiety',
    subCategory: 'test',
    text: '영어 테스트를 볼 때 평소 아는 것도 생각이 안 난다.',
    textEn: 'During English tests, I forget things I know.',
    reverse: false,
    weight: 1.1
  },
  {
    id: 11,
    category: 'anxiety',
    subCategory: 'test',
    text: '선생님 말씀을 못 알아들으면 불안해진다.',
    textEn: "I feel anxious when I don't understand what the teacher says.",
    reverse: false,
    weight: 1.0
  },
  {
    id: 12,
    category: 'anxiety',
    subCategory: 'test',
    text: '영어 발표나 시험 전날 밤 잠을 잘 못 잔다.',
    textEn: 'I have trouble sleeping before English presentations or tests.',
    reverse: false,
    weight: 1.2
  },
  // Low Self-Confidence (낮은 자신감) - 3문항
  {
    id: 13,
    category: 'anxiety',
    subCategory: 'confidence',
    text: '다른 학생들이 나보다 영어를 더 잘한다고 느낀다.',
    textEn: 'I feel other students are better at English than me.',
    reverse: false,
    weight: 1.0
  },
  {
    id: 14,
    category: 'anxiety',
    subCategory: 'confidence',
    text: '수업 시간에 영어로 말할 때 편안하다.',
    textEn: 'I feel confident when speaking English in class.',
    reverse: true,
    weight: 1.2
  },
  {
    id: 15,
    category: 'anxiety',
    subCategory: 'confidence',
    text: '내 영어 실력은 절대 좋아지지 않을 것 같다.',
    textEn: "I don't think my English will ever improve.",
    reverse: false,
    weight: 1.3
  },

  // ===== WTC (의사소통 의지) 영역 (15개) =====
  // Classroom WTC (수업 참여 의지) - 4문항
  {
    id: 16,
    category: 'wtc',
    subCategory: 'classroom',
    text: '수업 중 선생님 질문에 자발적으로 대답하고 싶다.',
    textEn: "I want to voluntarily answer the teacher's questions in class.",
    reverse: false,
    weight: 1.3
  },
  {
    id: 17,
    category: 'wtc',
    subCategory: 'classroom',
    text: '짝활동이나 그룹활동에서 영어로 적극 참여하고 싶다.',
    textEn: 'I want to actively participate in pair or group activities in English.',
    reverse: false,
    weight: 1.2
  },
  {
    id: 18,
    category: 'wtc',
    subCategory: 'classroom',
    text: '모르는 것이 있으면 영어로 질문하고 싶다.',
    textEn: "When I don't understand, I want to ask questions in English.",
    reverse: false,
    weight: 1.1
  },
  {
    id: 19,
    category: 'wtc',
    subCategory: 'classroom',
    text: '수업 시간에 내 의견을 영어로 표현하고 싶다.',
    textEn: 'I want to express my opinions in English during class.',
    reverse: false,
    weight: 1.2
  },
  // Social WTC (사회적 소통 의지) - 3문항
  {
    id: 20,
    category: 'wtc',
    subCategory: 'social',
    text: '외국인을 만나면 영어로 대화해 보고 싶다.',
    textEn: 'I want to try speaking English with foreigners.',
    reverse: false,
    weight: 1.1
  },
  {
    id: 21,
    category: 'wtc',
    subCategory: 'social',
    text: '영어를 사용하는 친구를 사귀고 싶다.',
    textEn: 'I want to make friends who speak English.',
    reverse: false,
    weight: 1.0
  },
  {
    id: 22,
    category: 'wtc',
    subCategory: 'social',
    text: '해외 여행 가서 적극적으로 영어를 쓰고 싶다.',
    textEn: 'I want to actively use English when traveling abroad.',
    reverse: false,
    weight: 1.1
  },
  // Self-Confidence in Communication (의사소통 자신감) - 3문항
  {
    id: 23,
    category: 'wtc',
    subCategory: 'confidence',
    text: '실수해도 괜찮으니 일단 영어로 말해보고 싶다.',
    textEn: 'I want to try speaking English even if I make mistakes.',
    reverse: false,
    weight: 1.3
  },
  {
    id: 24,
    category: 'wtc',
    subCategory: 'confidence',
    text: '내 영어 실력으로도 충분히 의사소통할 수 있다고 생각한다.',
    textEn: 'I believe I can communicate well with my current English skills.',
    reverse: false,
    weight: 1.2
  },
  {
    id: 25,
    category: 'wtc',
    subCategory: 'confidence',
    text: '영어로 말할 기회가 있으면 망설이지 않고 시도한다.',
    textEn: 'I try without hesitation when I have a chance to speak English.',
    reverse: false,
    weight: 1.3
  },
  // Intrinsic Motivation (내재적 동기) - 3문항
  {
    id: 26,
    category: 'wtc',
    subCategory: 'motivation',
    text: '영어로 말하는 것이 재미있다.',
    textEn: 'I find speaking English fun.',
    reverse: false,
    weight: 1.2
  },
  {
    id: 27,
    category: 'wtc',
    subCategory: 'motivation',
    text: '영어 실력을 늘리기 위해 더 많이 말하고 싶다.',
    textEn: 'I want to speak more to improve my English skills.',
    reverse: false,
    weight: 1.1
  },
  {
    id: 28,
    category: 'wtc',
    subCategory: 'motivation',
    text: '영어로 새로운 것을 배우는 것이 즐겁다.',
    textEn: 'I enjoy learning new things through English.',
    reverse: false,
    weight: 1.0
  },
  // Digital WTC (디지털 소통 의지) - 2문항
  {
    id: 29,
    category: 'wtc',
    subCategory: 'digital',
    text: 'SNS나 온라인에서 영어로 글을 쓰거나 댓글을 달고 싶다.',
    textEn: 'I want to write or comment in English on social media or online.',
    reverse: false,
    weight: 0.9
  },
  {
    id: 30,
    category: 'wtc',
    subCategory: 'digital',
    text: '온라인 게임이나 커뮤니티에서 영어로 대화하고 싶다.',
    textEn: 'I want to communicate in English in online games or communities.',
    reverse: false,
    weight: 0.9
  }
];

// Likert 옵션
const likertOptions = [
  { value: 5, label: '매우 그렇다', emoji: '😊' },
  { value: 4, label: '그렇다', emoji: '🙂' },
  { value: 3, label: '보통이다', emoji: '😐' },
  { value: 2, label: '그렇지 않다', emoji: '🙁' },
  { value: 1, label: '전혀 그렇지 않다', emoji: '😟' }
];

// 학년별 규준 데이터
const gradeNorms = {
  '초3': { anxiety: { mean: 3.2, sd: 0.8 }, wtc: { mean: 3.5, sd: 0.7 } },
  '초4': { anxiety: { mean: 3.1, sd: 0.8 }, wtc: { mean: 3.6, sd: 0.7 } },
  '초5': { anxiety: { mean: 3.3, sd: 0.9 }, wtc: { mean: 3.4, sd: 0.8 } },
  '초6': { anxiety: { mean: 3.4, sd: 0.9 }, wtc: { mean: 3.3, sd: 0.8 } },
  '중1': { anxiety: { mean: 3.5, sd: 0.9 }, wtc: { mean: 3.2, sd: 0.8 } },
  '중2': { anxiety: { mean: 3.6, sd: 1.0 }, wtc: { mean: 3.1, sd: 0.8 } },
  '중3': { anxiety: { mean: 3.7, sd: 1.0 }, wtc: { mean: 3.0, sd: 0.9 } },
  '고1': { anxiety: { mean: 3.6, sd: 1.0 }, wtc: { mean: 3.1, sd: 0.9 } },
  '고2': { anxiety: { mean: 3.5, sd: 1.0 }, wtc: { mean: 3.2, sd: 0.9 } },
  '고3': { anxiety: { mean: 3.4, sd: 1.0 }, wtc: { mean: 3.3, sd: 0.9 } }
};

// 하위 카테고리 라벨
const subCategoryLabels = {
  anxiety_communication: '의사소통 불안',
  anxiety_fear: '평가 두려움',
  anxiety_test: '시험/수행 불안',
  anxiety_confidence: '자신감 결여',
  wtc_classroom: '수업 참여 의지',
  wtc_social: '사회적 소통 의지',
  wtc_confidence: '소통 자신감',
  wtc_motivation: '내재적 동기',
  wtc_digital: '디지털 소통 의지'
};
