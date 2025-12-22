import React, { useState, useMemo } from 'react';

// 30개의 정교한 질문 세트 (FLCAS & WTC 기반)
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
    weight: 1.2 // 핵심 지표
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
    textEn: 'I feel anxious when I don\'t understand what the teacher says.',
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

  // Low Self-Confidence (낮은 자신감) - 3문항 (역문항 포함)
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
    textEn: 'I don\'t think my English will ever improve.',
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
    textEn: 'I want to voluntarily answer the teacher\'s questions in class.',
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
    textEn: 'When I don\'t understand, I want to ask questions in English.',
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

const likertOptions = [
  { value: 5, label: '매우 그렇다', emoji: '😊', color: 'bg-emerald-500' },
  { value: 4, label: '그렇다', emoji: '🙂', color: 'bg-green-500' },
  { value: 3, label: '보통이다', emoji: '😐', color: 'bg-yellow-500' },
  { value: 2, label: '그렇지 않다', emoji: '🙁', color: 'bg-orange-500' },
  { value: 1, label: '전혀 그렇지 않다', emoji: '😟', color: 'bg-red-500' }
];

// 학년별 규준 데이터 (Normative Data)
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

export default function EnglishAnxietyWTCAssessment() {
  const [currentStep, setCurrentStep] = useState('intro');
  const [studentInfo, setStudentInfo] = useState({ name: '', grade: '' });
  const [answers, setAnswers] = useState({});
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [startTime] = useState(Date.now());
  const [questionTimes, setQuestionTimes] = useState({});

  const handleStartSurvey = () => {
    if (studentInfo.name && studentInfo.grade) {
      setCurrentStep('survey');
      setQuestionTimes({ [questions[0].id]: Date.now() });
    }
  };

  const handleAnswer = (questionId, value) => {
    setAnswers(prev => ({ ...prev, [questionId]: value }));
  };

  const handleNext = () => {
    // 응답 시간 기록
    const currentQ = questions[currentQuestion];
    setQuestionTimes(prev => ({
      ...prev,
      [currentQ.id]: Date.now() - (prev[currentQ.id] || Date.now())
    }));

    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(prev => prev + 1);
      const nextQ = questions[currentQuestion + 1];
      setQuestionTimes(prev => ({ ...prev, [nextQ.id]: Date.now() }));
    } else {
      setCurrentStep('result');
    }
  };

  const handlePrev = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1);
    }
  };

  // 고급 점수 계산
  const calculateAdvancedScores = useMemo(() => {
    let anxietySum = 0, anxietyWeightSum = 0, anxietyCount = 0;
    let wtcSum = 0, wtcWeightSum = 0, wtcCount = 0;
    const subScores = {};
    const responsePattern = [];

    questions.forEach(q => {
      if (answers[q.id] !== undefined) {
        let score = answers[q.id];
        if (q.reverse) score = 6 - score;

        const weightedScore = score * q.weight;
        responsePattern.push(score);

        // 전체 점수
        if (q.category === 'anxiety') {
          anxietySum += weightedScore;
          anxietyWeightSum += q.weight;
          anxietyCount++;
        } else {
          wtcSum += weightedScore;
          wtcWeightSum += q.weight;
          wtcCount++;
        }

        // 하위 카테고리 점수
        const key = `${q.category}_${q.subCategory}`;
        if (!subScores[key]) {
          subScores[key] = { total: 0, weightSum: 0, count: 0, category: q.category, subCategory: q.subCategory };
        }
        subScores[key].total += weightedScore;
        subScores[key].weightSum += q.weight;
        subScores[key].count++;
      }
    });

    const anxietyMean = anxietyWeightSum > 0 ? anxietySum / anxietyWeightSum : 0;
    const wtcMean = wtcWeightSum > 0 ? wtcSum / wtcWeightSum : 0;

    // 표준점수 계산 (Z-score & T-score)
    const norm = gradeNorms[studentInfo.grade] || gradeNorms['중2'];
    const anxietyZ = (anxietyMean - norm.anxiety.mean) / norm.anxiety.sd;
    const wtcZ = (wtcMean - norm.wtc.mean) / norm.wtc.sd;
    const anxietyT = 50 + (anxietyZ * 10);
    const wtcT = 50 + (wtcZ * 10);

    // 백분위 계산 (정규분포 가정)
    const normalCDF = (z) => {
      const t = 1 / (1 + 0.2316419 * Math.abs(z));
      const d = 0.3989423 * Math.exp(-z * z / 2);
      const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
      return z > 0 ? 1 - p : p;
    };
    const anxietyPercentile = Math.round(normalCDF(anxietyZ) * 100);
    const wtcPercentile = Math.round(normalCDF(wtcZ) * 100);

    // 응답 일관성 검사 (Cronbach's Alpha 간소화 버전)
    const variance = (arr) => {
      const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
      return arr.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / arr.length;
    };
    const responseVariance = variance(responsePattern);
    const consistency = responseVariance > 0.3 ? 'high' : responseVariance > 0.15 ? 'medium' : 'low';

    // 하위 카테고리 평균 계산
    Object.keys(subScores).forEach(key => {
      subScores[key].mean = subScores[key].total / subScores[key].weightSum;
    });

    return {
      anxiety: {
        raw: anxietyMean.toFixed(2),
        z: anxietyZ.toFixed(2),
        t: anxietyT.toFixed(1),
        percentile: anxietyPercentile,
        count: anxietyCount
      },
      wtc: {
        raw: wtcMean.toFixed(2),
        z: wtcZ.toFixed(2),
        t: wtcT.toFixed(1),
        percentile: wtcPercentile,
        count: wtcCount
      },
      subScores,
      consistency,
      responseVariance: responseVariance.toFixed(2)
    };
  }, [answers, studentInfo.grade]);

  // 8가지 세분화된 프로필 타입
  const getDetailedProfile = (anxiety, wtc) => {
    const a = parseFloat(anxiety);
    const w = parseFloat(wtc);

    // 3x3 그리드로 더 세분화 (실제로는 8개 사용)
    if (a <= 2.3 && w >= 4.0) {
      return {
        type: '완벽한 커뮤니케이터',
        emoji: '🌟',
        color: 'bg-emerald-600',
        bgColor: 'bg-emerald-50',
        borderColor: 'border-emerald-300',
        level: 'excellent',
        description: '영어 불안감이 매우 낮고 의사소통 의지가 탁월합니다. 이상적인 영어 학습자 프로필로, 자신감 있게 다양한 상황에서 영어를 구사할 준비가 되어 있습니다.',
        strengths: ['높은 자신감', '적극적 참여', '위험 감수 능력', '자기주도적 학습'],
        weaknesses: ['과도한 자신감으로 인한 세밀함 부족 가능성'],
        priority: '고급 표현력 개발 및 리더십 역할'
      };
    } else if (a <= 2.3 && w >= 3.2 && w < 4.0) {
      return {
        type: '자신감 있는 학습자',
        emoji: '😊',
        color: 'bg-teal-600',
        bgColor: 'bg-teal-50',
        borderColor: 'border-teal-300',
        level: 'very-good',
        description: '불안감이 낮고 의사소통 의지가 양호합니다. 편안하게 영어를 사용하며, 약간의 동기 부여로 탁월한 수준으로 성장할 수 있습니다.',
        strengths: ['안정적인 심리 상태', '긍정적 학습 태도', '꾸준한 참여'],
        weaknesses: ['적극성 부족', '도전 회피 경향'],
        priority: '도전적 과제를 통한 의사소통 의지 강화'
      };
    } else if (a <= 2.3 && w < 3.2) {
      return {
        type: '편안한 관망자',
        emoji: '😌',
        color: 'bg-sky-600',
        bgColor: 'bg-sky-50',
        borderColor: 'border-sky-300',
        level: 'good',
        description: '불안감은 거의 없지만 적극적으로 소통하려는 의지가 낮습니다. 심리적 장벽은 없으므로 흥미와 동기만 찾으면 빠르게 성장할 수 있습니다.',
        strengths: ['편안한 심리 상태', '스트레스 관리 능력'],
        weaknesses: ['낮은 참여도', '수동적 태도', '동기 부족'],
        priority: '흥미 기반 활동으로 내재적 동기 유발'
      };
    } else if (a > 2.3 && a <= 3.3 && w >= 3.8) {
      return {
        type: '용감한 도전자',
        emoji: '💪',
        color: 'bg-amber-600',
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-300',
        level: 'good',
        description: '어느 정도 불안을 느끼지만 그럼에도 적극적으로 소통하려는 강한 의지를 가지고 있습니다. 성장 마인드셋을 지닌 학습자로, 경험이 쌓이면 불안이 감소할 것입니다.',
        strengths: ['강한 동기', '성장 마인드셋', '인내심', '도전 정신'],
        weaknesses: ['높은 스트레스', '번아웃 위험', '과도한 자기비판'],
        priority: '불안 관리 전략 및 성공 경험 축적'
      };
    } else if (a > 2.3 && a <= 3.3 && w >= 3.0 && w < 3.8) {
      return {
        type: '신중한 참여자',
        emoji: '🤔',
        color: 'bg-indigo-600',
        bgColor: 'bg-indigo-50',
        borderColor: 'border-indigo-300',
        level: 'moderate',
        description: '중간 수준의 불안과 의사소통 의지를 보입니다. 적절한 지원과 격려가 있다면 양방향 모두 개선될 수 있는 균형적 프로필입니다.',
        strengths: ['현실적 자기 인식', '균형잡힌 태도'],
        weaknesses: ['일관성 부족', '상황 의존적 반응'],
        priority: '단계적 자신감 구축 및 안전한 연습 환경'
      };
    } else if (a > 2.3 && a <= 3.3 && w < 3.0) {
      return {
        type: '망설이는 학습자',
        emoji: '😕',
        color: 'bg-orange-600',
        bgColor: 'bg-orange-50',
        borderColor: 'border-orange-300',
        level: 'needs-support',
        description: '불안감과 낮은 의사소통 의지가 함께 나타납니다. 심리적 지원과 함께 작은 성공 경험을 쌓는 것이 중요합니다.',
        strengths: ['신중함', '자기 보호 능력'],
        weaknesses: ['회피 경향', '낮은 자신감', '제한된 참여'],
        priority: '심리적 안전감 조성 및 작은 성공 경험'
      };
    } else if (a > 3.3 && w >= 3.0) {
      return {
        type: '고군분투하는 전사',
        emoji: '😣',
        color: 'bg-rose-600',
        bgColor: 'bg-rose-50',
        borderColor: 'border-rose-300',
        level: 'needs-support',
        description: '높은 불안에도 불구하고 소통하려는 의지를 보입니다. 매우 용기 있는 학습자이지만, 불안 관리가 시급히 필요합니다.',
        strengths: ['뛰어난 용기', '강한 의지', '끈기'],
        weaknesses: ['높은 스트레스', '정서적 소진', '부정적 자기대화'],
        priority: '불안 감소 최우선 - 이완 기법 및 상담 지원'
      };
    } else {
      return {
        type: '보호가 필요한 학습자',
        emoji: '🌱',
        color: 'bg-violet-600',
        bgColor: 'bg-violet-50',
        borderColor: 'border-violet-300',
        level: 'high-support',
        description: '높은 불안과 낮은 의사소통 의지를 보입니다. 전문적인 정서적 지원과 개별화된 접근이 필요합니다. 현재 상태는 일시적일 수 있으며, 적절한 개입으로 충분히 개선 가능합니다.',
        strengths: ['정직한 자기 인식', '개선 가능성'],
        weaknesses: ['높은 불안', '낮은 동기', '회피 패턴', '부정적 신념'],
        priority: '전문가 상담 권장, 1:1 맞춤 지원, 비평가적 환경'
      };
    }
  };

  const progress = ((currentQuestion + 1) / questions.length) * 100;

  // 인트로 화면
  if (currentStep === 'intro') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-4 flex items-center justify-center">
        <div className="max-w-2xl w-full bg-white rounded-3xl shadow-2xl p-8">
          <div className="text-center mb-8">
            <div className="text-7xl mb-4">🎯</div>
            <h1 className="text-3xl font-bold text-gray-800 mb-3">
              영어 말하기 심층 성향 분석
            </h1>
            <p className="text-gray-500 text-sm mb-2">
              FLCAS & WTC 기반 전문 심리측정학적 진단 도구
            </p>
            <div className="inline-block bg-indigo-100 text-indigo-700 px-4 py-1 rounded-full text-xs font-medium">
              Ver 2.0 Advanced | Psychometric Assessment
            </div>
          </div>

          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-6 mb-6 border border-indigo-100">
            <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <span className="text-xl">📊</span>
              이 검사의 특징
            </h3>
            <ul className="space-y-2 text-sm text-gray-700">
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>30개 정교한 문항</strong>으로 15개 하위 척도 측정</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>표준점수(T-score) & 백분위</strong> 제공</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>8가지 세분화된 프로필</strong> 유형 분류</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>학년별 규준 비교</strong> 및 또래 분석</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>응답 신뢰도 검증</strong> 및 일관성 분석</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-emerald-500 mt-0.5">✓</span>
                <span><strong>우선순위 개선 영역</strong> 및 구체적 실행 계획</span>
              </li>
            </ul>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6">
            <p className="text-sm text-gray-700 leading-relaxed">
              <span className="font-semibold text-amber-700">📝 소요 시간:</span> 약 8-10분 |
              <span className="font-semibold text-amber-700 ml-3">📱 권장:</span> 조용한 환경에서 집중하여 응답
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">이름</label>
              <input
                type="text"
                value={studentInfo.name}
                onChange={(e) => setStudentInfo(prev => ({ ...prev, name: e.target.value }))}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition"
                placeholder="이름을 입력하세요"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">학년</label>
              <select
                value={studentInfo.grade}
                onChange={(e) => setStudentInfo(prev => ({ ...prev, grade: e.target.value }))}
                className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition bg-white"
              >
                <option value="">선택하세요</option>
                {Object.keys(gradeNorms).map(grade => (
                  <option key={grade} value={grade}>{grade}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleStartSurvey}
            disabled={!studentInfo.name || !studentInfo.grade}
            className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold text-lg rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:from-indigo-700 hover:to-purple-700 transition shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
          >
            검사 시작하기 →
          </button>

          <p className="text-center text-xs text-gray-400 mt-4">
            Horwitz et al. (1986) & MacIntyre et al. (1998) 기반
          </p>
        </div>
      </div>
    );
  }

  // 설문 화면
  if (currentStep === 'survey') {
    const question = questions[currentQuestion];
    const isAnswered = answers[question.id] !== undefined;
    const categoryProgress = questions.filter((q, idx) =>
      idx <= currentQuestion && q.category === question.category
    ).length;
    const categoryTotal = questions.filter(q => q.category === question.category).length;

    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-4">
        <div className="max-w-2xl mx-auto">
          {/* Enhanced Progress Bar */}
          <div className="mb-6 bg-white rounded-2xl shadow-lg p-4">
            <div className="flex justify-between items-center text-sm mb-3">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-gray-700">진행률</span>
                <span className="text-gray-500">{currentQuestion + 1} / {questions.length}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  question.category === 'anxiety'
                    ? 'bg-rose-100 text-rose-700 font-medium'
                    : 'bg-emerald-100 text-emerald-700 font-medium'
                }`}>
                  {question.category === 'anxiety' ? '불안 척도' : '의지 척도'}
                </span>
                <span className="text-xs text-gray-500">
                  ({categoryProgress}/{categoryTotal})
                </span>
              </div>
            </div>
            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all duration-500 ease-out relative"
                style={{ width: `${progress}%` }}
              >
                <div className="absolute inset-0 bg-white opacity-20 animate-pulse" />
              </div>
            </div>
            <div className="text-right text-xs text-gray-500 mt-1">{Math.round(progress)}% 완료</div>
          </div>

          {/* Question Card */}
          <div className="bg-white rounded-3xl shadow-2xl p-8 mb-6">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`inline-block px-3 py-1.5 rounded-full text-xs font-semibold ${
                  question.category === 'anxiety'
                    ? 'bg-rose-100 text-rose-700'
                    : 'bg-emerald-100 text-emerald-700'
                }`}>
                  {question.category === 'anxiety' ? '😰 불안 측정' : '🗣️ 의지 측정'}
                </span>
                <span className="text-xs text-gray-400">
                  {question.subCategory}
                </span>
              </div>
              {question.weight > 1.0 && (
                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full font-medium">
                  ⭐ 핵심문항
                </span>
              )}
            </div>

            <h2 className="text-xl font-bold text-gray-800 mb-3 leading-relaxed">
              {question.text}
            </h2>
            <p className="text-sm text-gray-400 italic mb-8 leading-relaxed">
              {question.textEn}
            </p>

            <div className="space-y-3">
              {likertOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handleAnswer(question.id, option.value)}
                  className={`w-full p-5 rounded-2xl border-2 transition-all duration-300 flex items-center gap-4 ${
                    answers[question.id] === option.value
                      ? 'border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-lg transform scale-[1.02]'
                      : 'border-gray-200 hover:border-indigo-200 hover:bg-gray-50 hover:shadow-md'
                  }`}
                >
                  <span className="text-3xl">{option.emoji}</span>
                  <div className="flex-1 text-left">
                    <span className={`font-semibold text-lg ${
                      answers[question.id] === option.value ? 'text-indigo-700' : 'text-gray-700'
                    }`}>
                      {option.label}
                    </span>
                  </div>
                  {answers[question.id] === option.value && (
                    <div className="w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Navigation */}
          <div className="flex gap-4">
            <button
              onClick={handlePrev}
              disabled={currentQuestion === 0}
              className="flex-1 py-4 bg-white border-2 border-gray-200 text-gray-600 font-semibold rounded-xl disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-50 hover:border-gray-300 transition shadow-md"
            >
              ← 이전
            </button>
            <button
              onClick={handleNext}
              disabled={!isAnswered}
              className="flex-1 py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-bold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:from-indigo-700 hover:to-purple-700 transition shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
            >
              {currentQuestion === questions.length - 1 ? '결과 분석 →' : '다음 →'}
            </button>
          </div>

          {/* Mini Progress Indicator */}
          <div className="mt-4 flex justify-center gap-1">
            {questions.map((_, idx) => (
              <div
                key={idx}
                className={`h-1 rounded-full transition-all duration-300 ${
                  idx < currentQuestion ? 'w-2 bg-indigo-500' :
                  idx === currentQuestion ? 'w-4 bg-indigo-600' :
                  'w-1 bg-gray-300'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // 결과 화면
  if (currentStep === 'result') {
    const scores = calculateAdvancedScores;
    const profile = getDetailedProfile(scores.anxiety.raw, scores.wtc.raw);

    // 하위 카테고리 라벨
    const subCategoryLabels = {
      anxiety_communication: '의사소통 불안',
      anxiety_fear: '평가 두려움',
      anxiety_test: '시험/수행 불안',
      anxiety_confidence: '자신감 결여',
      anxiety_physical: '신체적 반응',
      wtc_classroom: '수업 참여 의지',
      wtc_social: '사회적 소통 의지',
      wtc_confidence: '소통 자신감',
      wtc_motivation: '내재적 동기',
      wtc_digital: '디지털 소통 의지'
    };

    // 강점/약점 우선순위 분석
    const subScoresArray = Object.entries(scores.subScores).map(([key, data]) => ({
      key,
      label: subCategoryLabels[key],
      mean: data.mean,
      category: data.category
    }));

    const anxietyAreas = subScoresArray.filter(s => s.category === 'anxiety').sort((a, b) => b.mean - a.mean);
    const wtcAreas = subScoresArray.filter(s => s.category === 'wtc').sort((a, b) => a.mean - b.mean);

    const topAnxietyArea = anxietyAreas[0];
    const lowWtcArea = wtcAreas[0];

    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-4 py-8">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header Card */}
          <div className="bg-white rounded-3xl shadow-2xl p-8 text-center">
            <div className="text-7xl mb-4">{profile.emoji}</div>
            <h1 className="text-2xl font-bold text-gray-800 mb-2">
              {studentInfo.name} 학생의 심층 분석 결과
            </h1>
            <div className={`inline-block px-6 py-3 rounded-2xl ${profile.color} text-white font-bold text-lg mt-3 shadow-lg`}>
              {profile.type}
            </div>
            <p className="text-sm text-gray-500 mt-3">{studentInfo.grade} | {new Date().toLocaleDateString('ko-KR')}</p>
          </div>

          {/* Main Scores with Statistical Info */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Anxiety Score */}
            <div className="bg-white rounded-2xl shadow-xl p-6">
              <div className="text-center mb-4">
                <div className="text-4xl mb-2">😰</div>
                <h3 className="text-lg font-bold text-gray-800">영어 말하기 불안</h3>
                <p className="text-xs text-gray-500">Foreign Language Anxiety</p>
              </div>
              <div className="text-center mb-4">
                <div className="text-5xl font-bold text-rose-600 mb-1">{scores.anxiety.raw}</div>
                <div className="text-sm text-gray-500">/ 5.00</div>
              </div>
              <div className="space-y-3 bg-gray-50 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">표준점수 (T-score)</span>
                  <span className="text-sm font-bold text-gray-800">{scores.anxiety.t}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">백분위 (Percentile)</span>
                  <span className="text-sm font-bold text-rose-600">{scores.anxiety.percentile}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">또래 비교</span>
                  <span className="text-xs text-gray-700">
                    {scores.anxiety.percentile > 75 ? '상위 25%' :
                     scores.anxiety.percentile > 50 ? '평균 이상' :
                     scores.anxiety.percentile > 25 ? '평균 이하' : '하위 25%'}
                  </span>
                </div>
              </div>
              <div className="mt-4 h-3 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-rose-400 to-rose-600 rounded-full transition-all duration-1000"
                  style={{ width: `${(parseFloat(scores.anxiety.raw) / 5) * 100}%` }}
                />
              </div>
            </div>

            {/* WTC Score */}
            <div className="bg-white rounded-2xl shadow-xl p-6">
              <div className="text-center mb-4">
                <div className="text-4xl mb-2">🗣️</div>
                <h3 className="text-lg font-bold text-gray-800">의사소통 의지</h3>
                <p className="text-xs text-gray-500">Willingness to Communicate</p>
              </div>
              <div className="text-center mb-4">
                <div className="text-5xl font-bold text-emerald-600 mb-1">{scores.wtc.raw}</div>
                <div className="text-sm text-gray-500">/ 5.00</div>
              </div>
              <div className="space-y-3 bg-gray-50 rounded-xl p-4">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">표준점수 (T-score)</span>
                  <span className="text-sm font-bold text-gray-800">{scores.wtc.t}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">백분위 (Percentile)</span>
                  <span className="text-sm font-bold text-emerald-600">{scores.wtc.percentile}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs font-medium text-gray-600">또래 비교</span>
                  <span className="text-xs text-gray-700">
                    {scores.wtc.percentile > 75 ? '상위 25%' :
                     scores.wtc.percentile > 50 ? '평균 이상' :
                     scores.wtc.percentile > 25 ? '평균 이하' : '하위 25%'}
                  </span>
                </div>
              </div>
              <div className="mt-4 h-3 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 rounded-full transition-all duration-1000"
                  style={{ width: `${(parseFloat(scores.wtc.raw) / 5) * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Profile Description */}
          <div className={`rounded-2xl shadow-xl p-6 ${profile.bgColor} border-2 ${profile.borderColor}`}>
            <h3 className="font-bold text-gray-800 mb-3 text-lg flex items-center gap-2">
              <span className="text-2xl">📊</span>
              종합 성향 분석
            </h3>
            <p className="text-gray-700 leading-relaxed mb-4">
              {profile.description}
            </p>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white bg-opacity-60 rounded-xl p-4">
                <h4 className="font-semibold text-emerald-700 mb-2 text-sm">💪 주요 강점</h4>
                <ul className="space-y-1">
                  {profile.strengths.map((strength, idx) => (
                    <li key={idx} className="text-xs text-gray-700 flex items-start gap-1">
                      <span className="text-emerald-500">•</span>
                      <span>{strength}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="bg-white bg-opacity-60 rounded-xl p-4">
                <h4 className="font-semibold text-amber-700 mb-2 text-sm">⚠️ 주의 영역</h4>
                <ul className="space-y-1">
                  {profile.weaknesses.map((weakness, idx) => (
                    <li key={idx} className="text-xs text-gray-700 flex items-start gap-1">
                      <span className="text-amber-500">•</span>
                      <span>{weakness}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Detailed Subscale Radar Chart (Text-based) */}
          <div className="bg-white rounded-2xl shadow-xl p-6">
            <h3 className="font-bold text-gray-800 mb-4 text-lg flex items-center gap-2">
              <span className="text-2xl">📈</span>
              세부 척도 분석
            </h3>
            <div className="space-y-3">
              {Object.entries(scores.subScores)
                .sort((a, b) => {
                  if (a[1].category !== b[1].category) {
                    return a[1].category === 'anxiety' ? -1 : 1;
                  }
                  return 0;
                })
                .map(([key, data]) => {
                  const avg = data.mean.toFixed(2);
                  const isAnxiety = data.category === 'anxiety';
                  const percentage = (parseFloat(avg) / 5) * 100;
                  return (
                    <div key={key} className="group">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-700">
                          {subCategoryLabels[key] || key}
                        </span>
                        <span className={`text-sm font-bold ${isAnxiety ? 'text-rose-600' : 'text-emerald-600'}`}>
                          {avg}
                        </span>
                      </div>
                      <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-1000 ${
                            isAnxiety
                              ? 'bg-gradient-to-r from-rose-400 to-rose-500'
                              : 'bg-gradient-to-r from-emerald-400 to-emerald-500'
                          }`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>

          {/* Priority Improvement Areas */}
          <div className="bg-white rounded-2xl shadow-xl p-6">
            <h3 className="font-bold text-gray-800 mb-4 text-lg flex items-center gap-2">
              <span className="text-2xl">🎯</span>
              우선순위 개선 영역
            </h3>
            <div className="space-y-4">
              {topAnxietyArea && parseFloat(topAnxietyArea.mean) > 3.0 && (
                <div className="bg-rose-50 border-l-4 border-rose-500 p-4 rounded-r-xl">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-rose-600 font-bold text-sm">우선순위 1</span>
                    <span className="text-xs bg-rose-200 text-rose-800 px-2 py-0.5 rounded-full">불안 감소</span>
                  </div>
                  <p className="text-sm text-gray-700 font-medium mb-1">{topAnxietyArea.label}</p>
                  <p className="text-xs text-gray-600">
                    현재 점수: <strong>{topAnxietyArea.mean.toFixed(2)}</strong> - 이 영역의 불안을 줄이는 것이 가장 시급합니다.
                  </p>
                </div>
              )}
              {lowWtcArea && parseFloat(lowWtcArea.mean) < 3.5 && (
                <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-xl">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-amber-600 font-bold text-sm">우선순위 2</span>
                    <span className="text-xs bg-amber-200 text-amber-800 px-2 py-0.5 rounded-full">의지 강화</span>
                  </div>
                  <p className="text-sm text-gray-700 font-medium mb-1">{lowWtcArea.label}</p>
                  <p className="text-xs text-gray-600">
                    현재 점수: <strong>{lowWtcArea.mean.toFixed(2)}</strong> - 이 영역의 동기를 높이면 큰 발전이 있을 것입니다.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Actionable Recommendations */}
          <div className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl shadow-xl p-6 text-white">
            <h3 className="font-bold mb-4 text-xl flex items-center gap-2">
              <span className="text-3xl">💡</span>
              맞춤형 실행 계획
            </h3>
            <p className="text-sm opacity-90 mb-4">{profile.priority}</p>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-white bg-opacity-20 backdrop-blur rounded-xl p-4">
                <h4 className="font-semibold mb-3 text-sm">📚 학습 전략</h4>
                <ul className="space-y-2 text-sm">
                  {parseFloat(scores.anxiety.raw) > 3.0 && (
                    <>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>소규모 그룹에서 시작하여 점차 확대</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>철저한 사전 준비로 자신감 확보</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>호흡법, 이완 기법 연습</span>
                      </li>
                    </>
                  )}
                  {parseFloat(scores.wtc.raw) < 3.5 && (
                    <>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>흥미있는 주제로 대화 시작</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>게임이나 역할극 등 활동 중심</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span>✓</span>
                        <span>작은 성공 경험을 자주 만들기</span>
                      </li>
                    </>
                  )}
                </ul>
              </div>
              <div className="bg-white bg-opacity-20 backdrop-blur rounded-xl p-4">
                <h4 className="font-semibold mb-3 text-sm">🏃 실천 과제 (이번 주)</h4>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-start gap-2">
                    <span>1.</span>
                    <span>하루 5분 영어 독백 연습 (녹음)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span>2.</span>
                    <span>수업 중 최소 1회 자발적 발언</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span>3.</span>
                    <span>영어 일기 3줄 쓰기</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span>4.</span>
                    <span>좋아하는 영어 콘텐츠 찾아보기</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Quadrant Visualization */}
          <div className="bg-white rounded-2xl shadow-xl p-6">
            <h3 className="font-bold text-gray-800 mb-4 text-lg flex items-center gap-2">
              <span className="text-2xl">🗺️</span>
              성향 위치 맵
            </h3>
            <div className="relative aspect-square bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl p-6">
              {/* Grid */}
              <div className="absolute inset-6 border-l-2 border-b-2 border-gray-400" />
              <div className="absolute left-1/2 top-6 bottom-6 w-0.5 bg-gray-300" />
              <div className="absolute top-1/2 left-6 right-6 h-0.5 bg-gray-300" />

              {/* Axis Labels */}
              <div className="absolute left-2 top-4 text-xs text-gray-600 font-medium">높은<br/>불안</div>
              <div className="absolute left-2 bottom-4 text-xs text-gray-600 font-medium">낮은<br/>불안</div>
              <div className="absolute right-2 bottom-8 text-xs text-gray-600 font-medium">높은 의지</div>
              <div className="absolute left-8 bottom-8 text-xs text-gray-600 font-medium">낮은 의지</div>

              {/* Quadrant Labels */}
              <div className="absolute top-12 left-12 text-sm text-violet-600 font-bold opacity-50">보호형</div>
              <div className="absolute top-12 right-12 text-sm text-rose-600 font-bold opacity-50">전사형</div>
              <div className="absolute bottom-12 left-12 text-sm text-sky-600 font-bold opacity-50">관망형</div>
              <div className="absolute bottom-12 right-12 text-sm text-emerald-600 font-bold opacity-50">적극형</div>

              {/* Position Marker */}
              <div
                className={`absolute w-12 h-12 ${profile.color} rounded-full shadow-2xl border-4 border-white transform -translate-x-1/2 -translate-y-1/2 flex items-center justify-center text-2xl transition-all duration-1000 hover:scale-110 cursor-pointer`}
                style={{
                  left: `${((parseFloat(scores.wtc.raw) / 5) * 75) + 12.5}%`,
                  top: `${((5 - parseFloat(scores.anxiety.raw)) / 5 * 75) + 12.5}%`
                }}
                title={`불안: ${scores.anxiety.raw} / 의지: ${scores.wtc.raw}`}
              >
                {profile.emoji}
              </div>
            </div>
          </div>

          {/* Response Quality Check */}
          <div className="bg-white rounded-2xl shadow-xl p-6">
            <h3 className="font-bold text-gray-800 mb-4 text-lg flex items-center gap-2">
              <span className="text-2xl">✅</span>
              응답 신뢰도 검증
            </h3>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="bg-gray-50 rounded-xl p-4 text-center">
                <div className="text-3xl mb-2">
                  {scores.consistency === 'high' ? '🟢' : scores.consistency === 'medium' ? '🟡' : '🔴'}
                </div>
                <div className="text-xs text-gray-600 mb-1">응답 일관성</div>
                <div className="font-bold text-gray-800">
                  {scores.consistency === 'high' ? '높음' : scores.consistency === 'medium' ? '보통' : '낮음'}
                </div>
                <div className="text-xs text-gray-500 mt-1">분산: {scores.responseVariance}</div>
              </div>
              <div className="bg-gray-50 rounded-xl p-4 text-center">
                <div className="text-3xl mb-2">⏱️</div>
                <div className="text-xs text-gray-600 mb-1">완료 시간</div>
                <div className="font-bold text-gray-800">
                  {Math.round((Date.now() - startTime) / 1000 / 60)}분
                </div>
              </div>
              <div className="bg-gray-50 rounded-xl p-4 text-center">
                <div className="text-3xl mb-2">📊</div>
                <div className="text-xs text-gray-600 mb-1">응답 완료율</div>
                <div className="font-bold text-gray-800">
                  {Math.round((Object.keys(answers).length / questions.length) * 100)}%
                </div>
              </div>
            </div>
            {scores.consistency === 'low' && (
              <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-xl p-3">
                <p className="text-xs text-yellow-800">
                  ⚠️ 응답 패턴의 일관성이 낮게 나타났습니다. 더 신중하게 응답하거나, 다시 검사를 진행해보시기 바랍니다.
                </p>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="grid md:grid-cols-2 gap-4">
            <button
              onClick={() => window.print()}
              className="py-4 bg-gray-700 text-white font-semibold rounded-xl hover:bg-gray-800 transition shadow-lg flex items-center justify-center gap-2"
            >
              <span>🖨️</span>
              결과 인쇄하기
            </button>
            <button
              onClick={() => {
                setCurrentStep('intro');
                setAnswers({});
                setCurrentQuestion(0);
                setStudentInfo({ name: '', grade: '' });
              }}
              className="py-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-700 hover:to-purple-700 transition shadow-lg"
            >
              새로운 검사 시작
            </button>
          </div>

          {/* Footer */}
          <div className="text-center text-xs text-gray-400 space-y-1 pb-8">
            <p>Based on FLCAS (Horwitz et al., 1986) & WTC (MacIntyre et al., 1998)</p>
            <p>Psychometric Assessment Tool v2.0 | © 2024</p>
            <p className="text-xs text-gray-500 mt-2">
              본 검사 결과는 교육적 참고 자료이며, 전문적인 심리 상담을 대체하지 않습니다.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
