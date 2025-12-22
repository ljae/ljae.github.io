// 상황 기반 질문 데이터 (Scenario-Based Assessment)
const questions = [
  // ===== ANXIETY 영역 (15개) =====
  // Communication Apprehension (의사소통 불안) - 5문항
  {
    id: 1,
    category: 'anxiety',
    subCategory: 'communication',
    situation: '영어 수업 시간, 선생님이 "오늘 배운 내용을 짝과 영어로 이야기해보세요"라고 말씀하십니다.',
    text: '이 순간 당신은 어떤 생각이 드나요?',
    textEn: 'During English class, the teacher says, "Discuss today\'s lesson with your partner in English." What goes through your mind?',
    options: {
      5: '좋아, 재미있겠다!',
      4: '할 수 있을 것 같아',
      3: '음... 어떻게 시작하지?',
      2: '뭐라고 말해야 할지 모르겠어',
      1: '정말 하기 싫다, 피하고 싶어'
    },
    reverse: false,
    weight: 1.2
  },
  {
    id: 2,
    category: 'anxiety',
    subCategory: 'communication',
    situation: '영어로 발표 준비를 하고 있습니다. 선생님이 갑자기 "지금 준비한 것 중 일부만 먼저 발표해볼까요?"라고 하십니다.',
    text: '당신의 반응은?',
    textEn: 'You\'re preparing an English presentation when the teacher suddenly says, "Why don\'t you present what you\'ve prepared so far?" How do you react?',
    options: {
      5: '네! 지금 보여드릴게요',
      4: '조금 긴장되지만 할 수 있어요',
      3: '심장이 빨리 뛰지만 해볼게요',
      2: '머리가 하얘져서 생각이 안 나요',
      1: '패닉 상태, 아무 말도 못하겠어요'
    },
    reverse: false,
    weight: 1.1
  },
  {
    id: 3,
    category: 'anxiety',
    subCategory: 'communication',
    situation: '학급 전체 앞에서 영어로 자기소개를 해야 합니다. 당신의 차례가 5분 후입니다.',
    text: '지금 당신의 상태는?',
    textEn: 'You need to introduce yourself in English in front of the whole class. Your turn is in 5 minutes. How do you feel?',
    options: {
      5: '준비한 걸 잘 말할 수 있을 거야',
      4: '약간 떨리지만 괜찮아',
      3: '계속 연습하면서 긴장하고 있어',
      2: '손에 땀이 나고 목소리가 떨려',
      1: '화장실에 가고 싶어, 도망가고 싶어'
    },
    reverse: false,
    weight: 1.0
  },
  {
    id: 4,
    category: 'anxiety',
    subCategory: 'communication',
    situation: '원어민 선생님이 당신에게 영어로 "주말에 뭐 했어요?"라고 갑자기 물어봅니다.',
    text: '당신의 첫 반응은?',
    textEn: 'A native English teacher suddenly asks you in English, "What did you do this weekend?" What\'s your first reaction?',
    options: {
      5: '바로 답변할 수 있어요',
      4: '잠깐 생각하고 대답해요',
      3: '간단하게라도 말해봐요',
      2: '머릿속이 하얘져서 더듬거려요',
      1: '"I don\'t know" 밖에 안 나와요'
    },
    reverse: false,
    weight: 1.1
  },
  {
    id: 5,
    category: 'anxiety',
    subCategory: 'communication',
    situation: '영어 단어 발음이 확실하지 않은데, 큰 소리로 읽어야 하는 상황입니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You\'re not sure about the pronunciation of an English word, but you need to read it aloud. What do you do?',
    options: {
      5: '자신 있게 읽고 틀리면 배우면 돼',
      4: '최선을 다해 읽어봐요',
      3: '조용히 읽으면서 눈치를 봐요',
      2: '발음이 이상할까 봐 아주 작게 읽어요',
      1: '건너뛰거나 다른 사람이 읽기를 기다려요'
    },
    reverse: false,
    weight: 0.9
  },

  // Fear of Negative Evaluation (부정적 평가 두려움) - 4문항
  {
    id: 6,
    category: 'anxiety',
    subCategory: 'fear',
    situation: '영어로 발표했는데, 친구 몇 명이 웃었습니다. (실수 때문인지 다른 이유인지 모름)',
    text: '당신은 어떻게 생각하나요?',
    textEn: 'After presenting in English, some classmates laugh. (You\'re not sure if it\'s because of a mistake.) What do you think?',
    options: {
      5: '별일 아니야, 웃을 만한 다른 이유겠지',
      4: '조금 신경 쓰이지만 넘어가요',
      3: '내가 실수했나? 계속 생각나요',
      2: '분명 내 영어가 이상해서 웃었을 거야',
      1: '너무 창피해, 다시는 발표 못 해'
    },
    reverse: false,
    weight: 1.3
  },
  {
    id: 7,
    category: 'anxiety',
    subCategory: 'fear',
    situation: '선생님이 당신의 영어 문장을 칠판에 쓰시면서 "여기를 고쳐볼까요?"라고 하십니다.',
    text: '당신의 기분은?',
    textEn: 'The teacher writes your English sentence on the board and says, "Shall we correct this?" How do you feel?',
    options: {
      5: '좋아요, 배울 수 있는 기회네요',
      4: '괜찮아요, 실수는 당연한 거니까',
      3: '조금 부끄럽지만 참을 만해요',
      2: '얼굴이 빨개지고 창피해요',
      1: '모두가 나를 보고 있는 것 같아 견딜 수 없어요'
    },
    reverse: false,
    weight: 1.0
  },
  {
    id: 8,
    category: 'anxiety',
    subCategory: 'fear',
    situation: '영어 동아리 첫날, 다른 친구들은 모두 유창하게 영어로 대화하고 있습니다.',
    text: '당신은 어떻게 느끼나요?',
    textEn: 'On your first day at English club, everyone else is speaking English fluently. How do you feel?',
    options: {
      5: '배울 점이 많겠네, 도전해봐야지',
      4: '조금 뒤처지는 것 같지만 따라갈 거야',
      3: '내 수준이 낮은 것 같아 불안해요',
      2: '여기 있으면 안 될 것 같아요',
      1: '나만 못하는 것 같아서 그만두고 싶어요'
    },
    reverse: false,
    weight: 1.2
  },
  {
    id: 9,
    category: 'anxiety',
    subCategory: 'fear',
    situation: '영어 말하기 평가에서 실수를 했습니다. 친구들이 당신 차례가 끝난 후 수군거립니다.',
    text: '당신은 어떤 생각이 드나요?',
    textEn: 'You made a mistake during an English speaking test. Classmates whisper after your turn. What do you think?',
    options: {
      5: '다른 얘기하는 거겠지, 신경 안 써',
      4: '좀 찝찝하지만 넘어가요',
      3: '나에 대해 얘기하는 건 아닐까 신경 쓰여요',
      2: '분명 내 실수를 비웃는 거야',
      1: '너무 수치스러워, 학교 가기 싫어'
    },
    reverse: false,
    weight: 1.1
  },

  // Test Anxiety (시험/수행 불안) - 3문항
  {
    id: 10,
    category: 'anxiety',
    subCategory: 'test',
    situation: '영어 말하기 시험이 10분 후입니다. 분명 연습했던 문장인데...',
    text: '당신의 상태는?',
    textEn: 'Your English speaking test is in 10 minutes. You definitely practiced these sentences, but... How are you doing?',
    options: {
      5: '연습한 대로만 하면 돼, 차분해요',
      4: '약간 긴장되지만 기억나요',
      3: '연습한 게 가물가물해요',
      2: '머릿속이 백지가 된 것 같아요',
      1: '아무것도 생각 안 나요, 포기 상태예요'
    },
    reverse: false,
    weight: 1.1
  },
  {
    id: 11,
    category: 'anxiety',
    subCategory: 'test',
    situation: '듣기 평가 중 선생님이 빠르게 영어로 설명하십니다. 한 단어를 놓쳤습니다.',
    text: '당신의 반응은?',
    textEn: 'During a listening test, the teacher explains something quickly in English. You missed one word. What\'s your reaction?',
    options: {
      5: '문맥으로 유추할 수 있어요',
      4: '나머지로 이해하면 돼요',
      3: '그 부분만 계속 생각나서 집중이 안 돼요',
      2: '전체를 못 알아들은 것 같아 불안해요',
      1: '완전히 패닉, 나머지도 다 놓쳐요'
    },
    reverse: false,
    weight: 1.0
  },
  {
    id: 12,
    category: 'anxiety',
    subCategory: 'test',
    situation: '내일 영어 발표 시험입니다. 잠자리에 누웠는데...',
    text: '당신은 어떤가요?',
    textEn: 'You have an English presentation test tomorrow. You\'re lying in bed... How are you?',
    options: {
      5: '준비 잘 했으니 푹 자요',
      4: '조금 설레지만 잘 수 있어요',
      3: '한두 시간 뒤척이다 자요',
      2: '계속 연습하며 뒤척여요',
      1: '거의 밤을 새워요'
    },
    reverse: false,
    weight: 1.2
  },

  // Low Self-Confidence (낮은 자신감) - 3문항
  {
    id: 13,
    category: 'anxiety',
    subCategory: 'confidence',
    situation: '영어 수업에서 자원자를 찾습니다. 당신은 답을 알고 있습니다. 다른 친구들도 손을 들고 있습니다.',
    text: '당신의 생각은?',
    textEn: 'The teacher is looking for volunteers in English class. You know the answer. Other students are also raising their hands. What do you think?',
    options: {
      5: '손을 들어요, 내 답이 맞을 거야',
      4: '손을 들어요, 틀려도 괜찮아',
      3: '손을 들까 말까 망설여요',
      2: '다른 애들이 더 잘 알 거야, 안 들어요',
      1: '절대 손 안 들어요, 틀릴까 봐 무서워요'
    },
    reverse: false,
    weight: 1.0
  },
  {
    id: 14,
    category: 'anxiety',
    subCategory: 'confidence',
    situation: '영어 토론 수업입니다. 자유롭게 의견을 나누는 시간입니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'It\'s English debate class. It\'s time for free discussion. What do you do?',
    options: {
      5: '적극적으로 내 생각을 영어로 말해요',
      4: '준비되면 말해요',
      3: '누가 먼저 말해주길 기다려요',
      2: '거의 말하지 않아요',
      1: '전혀 말하지 않아요'
    },
    reverse: true,
    weight: 1.2
  },
  {
    id: 15,
    category: 'anxiety',
    subCategory: 'confidence',
    situation: '영어 실력이 늘지 않는 것 같습니다. 친구가 "너 영어 많이 늘었다"고 합니다.',
    text: '당신의 반응은?',
    textEn: 'You don\'t feel like your English is improving. A friend says, "Your English has gotten much better." How do you react?',
    options: {
      5: '고마워! 노력한 보람이 있네',
      4: '정말? 그렇다니 다행이야',
      3: '그냥 위로하는 말이겠지',
      2: '아니야, 전혀 안 늘었어',
      1: '나는 영어 절대 못해, 포기해야겠어'
    },
    reverse: false,
    weight: 1.3
  },

  // ===== WTC (의사소통 의지) 영역 (15개) =====
  // Classroom WTC (수업 참여 의지) - 4문항
  {
    id: 16,
    category: 'wtc',
    subCategory: 'classroom',
    situation: '선생님이 "오늘 배운 표현으로 자유롭게 문장을 만들어볼 사람?"이라고 물으십니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'The teacher asks, "Who wants to make a sentence using today\'s expressions?" What do you do?',
    options: {
      5: '바로 손을 들고 문장을 만들어봐요',
      4: '생각을 정리하고 손을 들어요',
      3: '하고 싶지만 망설여져요',
      2: '다른 사람이 하기를 기다려요',
      1: '절대 안 해요'
    },
    reverse: false,
    weight: 1.3
  },
  {
    id: 17,
    category: 'wtc',
    subCategory: 'classroom',
    situation: '그룹 활동에서 영어로 프로젝트를 발표할 대표를 뽑습니다.',
    text: '당신의 선택은?',
    textEn: 'Your group needs to choose a representative to present your project in English. What do you choose?',
    options: {
      5: '제가 할게요! 자원해요',
      4: '뽑히면 할게요',
      3: '다른 친구가 더 잘할 것 같아요',
      2: '발표는 안 하고 싶어요',
      1: '절대 안 해요, 다른 걸 하겠어요'
    },
    reverse: false,
    weight: 1.2
  },
  {
    id: 18,
    category: 'wtc',
    subCategory: 'classroom',
    situation: '수업 중 이해가 안 되는 부분이 있습니다. 선생님이 "질문 있나요?"라고 물으십니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'There\'s something you don\'t understand in class. The teacher asks, "Any questions?" What do you do?',
    options: {
      5: '바로 손들고 영어로 질문해요',
      4: '영어로 어떻게 물을지 생각하고 질문해요',
      3: '수업 끝나고 따로 물어봐요',
      2: '친구에게 나중에 물어봐요',
      1: '그냥 넘어가요'
    },
    reverse: false,
    weight: 1.1
  },
  {
    id: 19,
    category: 'wtc',
    subCategory: 'classroom',
    situation: '수업 중 선생님이 토론 주제를 주시고 "자유롭게 영어로 대화해보세요"라고 하십니다.',
    text: '당신의 참여도는?',
    textEn: 'The teacher gives a debate topic and says, "Discuss freely in English." How much do you participate?',
    options: {
      5: '적극적으로 내 의견을 많이 말해요',
      4: '여러 번 의견을 내요',
      3: '한두 번 정도 말해요',
      2: '듣기만 하고 거의 안 말해요',
      1: '전혀 참여 안 해요'
    },
    reverse: false,
    weight: 1.2
  },

  // Social WTC (사회적 소통 의지) - 3문항
  {
    id: 20,
    category: 'wtc',
    subCategory: 'social',
    situation: '길에서 길을 잃은 외국인 관광객을 만났습니다. 그들이 당신을 쳐다봅니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You meet lost foreign tourists on the street. They look at you. What do you do?',
    options: {
      5: '먼저 다가가서 "도와드릴까요?"라고 영어로 물어봐요',
      4: '그들이 물으면 영어로 도와줘요',
      3: '도와주고 싶지만 망설여져요',
      2: '못 본 척하고 지나가요',
      1: '피해서 가요'
    },
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
    options: {
      5: '다가가서 영어로 말을 걸어요',
      4: '친구와 함께 가서 말을 걸어요',
      3: '말 걸고 싶지만 용기가 안 나요',
      2: '웃음만 보내요',
      1: '아무것도 안 해요'
    },
    reverse: false,
    weight: 1.0
  },
  {
    id: 22,
    category: 'wtc',
    subCategory: 'social',
    situation: '해외여행 중입니다. 맛있어 보이는 음식을 발견했는데 메뉴판을 읽을 수 없습니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You\'re traveling abroad and find delicious-looking food, but can\'t read the menu. What do you do?',
    options: {
      5: '직원에게 영어로 물어봐요',
      4: '간단한 영어로 주문해봐요',
      3: '번역기 쓰면서 주문해요',
      2: '다른 곳으로 가요',
      1: '그냥 안 먹어요'
    },
    reverse: false,
    weight: 1.1
  },

  // Self-Confidence in Communication (의사소통 자신감) - 3문항
  {
    id: 23,
    category: 'wtc',
    subCategory: 'confidence',
    situation: '영어 캠프에서 즉흥 스피치 기회가 있습니다. 주제는 "나의 꿈"입니다.',
    text: '당신의 선택은?',
    textEn: 'There\'s an impromptu speech opportunity at English camp. The topic is "My Dream." What do you choose?',
    options: {
      5: '도전해요! 완벽하지 않아도 괜찮아요',
      4: '준비 시간을 조금 받고 해봐요',
      3: '하고 싶지만 너무 떨려요',
      2: '구경만 해요',
      1: '절대 안 해요'
    },
    reverse: false,
    weight: 1.3
  },
  {
    id: 24,
    category: 'wtc',
    subCategory: 'confidence',
    situation: '영어 대화 앱에서 원어민과 1:1 대화 기회가 생겼습니다.',
    text: '당신의 반응은?',
    textEn: 'You have a chance for 1:1 conversation with a native speaker on an English conversation app. What\'s your reaction?',
    options: {
      5: '바로 신청해요, 좋은 기회예요',
      4: '조금 긴장되지만 해봐요',
      3: '많이 고민하다가 안 해요',
      2: '너무 부담스러워요',
      1: '상상도 못 해요'
    },
    reverse: false,
    weight: 1.2
  },
  {
    id: 25,
    category: 'wtc',
    subCategory: 'confidence',
    situation: '영어 말하기 대회 안내문을 받았습니다. 상금도 있고 스펙에도 좋습니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You received a notice about an English speaking contest. There are prizes and it\'s good for your resume. What do you do?',
    options: {
      5: '도전해봐요, 경험이 중요해요',
      4: '준비할 시간 보고 결정해요',
      3: '관심은 있지만 엄두가 안 나요',
      2: '나랑은 상관없는 일이에요',
      1: '생각도 안 해봐요'
    },
    reverse: false,
    weight: 1.3
  },

  // Intrinsic Motivation (내재적 동기) - 3문항
  {
    id: 26,
    category: 'wtc',
    subCategory: 'motivation',
    situation: '주말입니다. 친구가 "영어로 영화 보면서 따라 말해볼래?"라고 제안합니다.',
    text: '당신의 반응은?',
    textEn: 'It\'s the weekend. A friend suggests, "Want to watch a movie in English and repeat after it?" How do you react?',
    options: {
      5: '좋아! 재미있겠다, 바로 해요',
      4: '괜찮을 것 같아요, 해봐요',
      3: '별로 내키지 않지만 따라해요',
      2: '그냥 한글 자막으로 봐요',
      1: '영어는 싫어요, 다른 걸 해요'
    },
    reverse: false,
    weight: 1.2
  },
  {
    id: 27,
    category: 'wtc',
    subCategory: 'motivation',
    situation: '유튜브에서 영어로 된 재미있는 컨텐츠를 발견했습니다. 자막이 없습니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You found interesting English content on YouTube. There are no subtitles. What do you do?',
    options: {
      5: '영어 그대로 보면서 이해해봐요',
      4: '모르는 단어 찾아가며 봐요',
      3: '자막 있는 거 찾아봐요',
      2: '포기하고 다른 영상 찾아요',
      1: '영어 콘텐츠는 안 봐요'
    },
    reverse: false,
    weight: 1.1
  },
  {
    id: 28,
    category: 'wtc',
    subCategory: 'motivation',
    situation: '영어 일기를 쓰면 선생님이 피드백을 주신다고 합니다. (선택 과제)',
    text: '당신의 선택은?',
    textEn: 'The teacher will give feedback if you write an English diary. (Optional assignment) What do you choose?',
    options: {
      5: '매일 써요, 배우는 게 좋아요',
      4: '일주일에 몇 번 써요',
      3: '한두 번 써봐요',
      2: '쓰고 싶지만 안 써요',
      1: '전혀 안 써요'
    },
    reverse: false,
    weight: 1.0
  },

  // Digital WTC (디지털 소통 의지) - 2문항
  {
    id: 29,
    category: 'wtc',
    subCategory: 'digital',
    situation: '좋아하는 해외 연예인이 SNS에 질문을 받고 있습니다. 영어로 댓글을 달면 답글을 받을 수도 있습니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'Your favorite foreign celebrity is taking questions on social media. If you comment in English, you might get a reply. What do you do?',
    options: {
      5: '영어로 댓글을 남겨요',
      4: '번역기 도움 받아서 써요',
      3: '쓰고 싶지만 용기가 안 나요',
      2: '좋아요만 눌러요',
      1: '아무것도 안 해요'
    },
    reverse: false,
    weight: 0.9
  },
  {
    id: 30,
    category: 'wtc',
    subCategory: 'digital',
    situation: '온라인 게임에서 외국인 팀원을 만났습니다. 영어로 소통하면 더 재미있을 것 같습니다.',
    text: '당신은 어떻게 하나요?',
    textEn: 'You met foreign teammates in an online game. It would be more fun to communicate in English. What do you do?',
    options: {
      5: '간단한 영어로라도 대화해요',
      4: '게임 용어 정도는 영어로 해요',
      3: '이모티콘만 써요',
      2: '채팅 안 해요',
      1: '그냥 나가요'
    },
    reverse: false,
    weight: 0.9
  }
];

// Likert 옵션은 이제 각 질문에 포함되어 있음
// 하지만 공통 인터페이스를 위해 유지
const likertOptions = [
  { value: 5, label: '매우 그렇다', emoji: '😊' },
  { value: 4, label: '그렇다', emoji: '🙂' },
  { value: 3, label: '보통이다', emoji: '😐' },
  { value: 2, label: '그렇지 않다', emoji: '🙁' },
  { value: 1, label: '전혀 그렇지 않다', emoji: '😟' }
];

// 학년별 규준 데이터 (동일 유지)
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
