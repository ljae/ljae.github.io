// 전역 상태
let currentStep = 'intro';  // 'intro', 'survey', 'result'
let studentInfo = { name: '', grade: '' };
let answers = {};
let currentQuestion = 0;
let startTime = Date.now();

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 이름/학년 입력 감지
    document.getElementById('student-name').addEventListener('input', validateForm);
    document.getElementById('student-grade').addEventListener('change', validateForm);
});

function validateForm() {
    const name = document.getElementById('student-name').value.trim();
    const grade = document.getElementById('student-grade').value;
    const startButton = document.getElementById('start-button');

    if (name && grade) {
        startButton.disabled = false;
    } else {
        startButton.disabled = true;
    }
}

function startSurvey() {
    studentInfo.name = document.getElementById('student-name').value.trim();
    studentInfo.grade = document.getElementById('student-grade').value;

    currentStep = 'survey';
    document.getElementById('intro-screen').classList.add('hidden');
    document.getElementById('survey-screen').classList.remove('hidden');

    startTime = Date.now();
    loadQuestion(0);
}

function loadQuestion(index) {
    currentQuestion = index;
    const question = questions[index];

    // Progress 업데이트
    const progress = ((index + 1) / questions.length) * 100;
    document.getElementById('current-question-num').textContent = index + 1;
    document.getElementById('progress-bar').style.width = progress + '%';
    document.getElementById('progress-percent').textContent = Math.round(progress);

    // 카테고리 배지 제거 (측정 의도 숨김)

    // 상황 설명 + 질문 텍스트
    const questionHTML = `
        <div class="bg-indigo-50 border-l-4 border-indigo-500 p-4 rounded-r-xl mb-4">
            <p class="text-sm font-medium text-indigo-900">📖 상황</p>
            <p class="text-gray-700 mt-1">${question.situation}</p>
        </div>
    `;
    document.getElementById('question-text').innerHTML = questionHTML + '<span class="text-lg font-bold text-gray-800">' + question.text + '</span>';
    document.getElementById('question-text-en').textContent = question.textEn;

    // 답변 옵션 생성 (상황별 맞춤 옵션)
    const optionsContainer = document.getElementById('answer-options');
    optionsContainer.innerHTML = '';

    // options 객체를 배열로 변환 (값이 큰 것부터 = 긍정적인 것부터)
    const optionEntries = Object.entries(question.options).sort((a, b) => b[0] - a[0]);

    optionEntries.forEach(([value, label]) => {
        const numValue = parseInt(value);
        const button = document.createElement('button');
        button.className = 'w-full p-5 rounded-2xl border-2 transition-all duration-300 flex items-center gap-4';

        const isSelected = answers[question.id] === numValue;
        if (isSelected) {
            button.className += ' border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-lg transform scale-[1.02]';
        } else {
            button.className += ' border-gray-200 hover:border-indigo-200 hover:bg-gray-50 hover:shadow-md';
        }

        button.onclick = () => selectAnswer(question.id, numValue);

        // 점수에 따른 이모지
        const emojis = { 5: '😊', 4: '🙂', 3: '😐', 2: '🙁', 1: '😟' };
        const emoji = document.createElement('span');
        emoji.className = 'text-3xl';
        emoji.textContent = emojis[numValue];

        const labelDiv = document.createElement('div');
        labelDiv.className = 'flex-1 text-left';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'font-semibold text-base leading-snug ' + (isSelected ? 'text-indigo-700' : 'text-gray-700');
        labelSpan.textContent = label;

        labelDiv.appendChild(labelSpan);

        if (isSelected) {
            const checkmark = document.createElement('div');
            checkmark.className = 'w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center flex-shrink-0';
            checkmark.innerHTML = '<svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>';
            button.appendChild(checkmark);
        }

        button.appendChild(emoji);
        button.appendChild(labelDiv);

        optionsContainer.appendChild(button);
    });

    // 네비게이션 버튼 상태
    document.getElementById('prev-button').disabled = (index === 0);
    updateNextButton();
}

function selectAnswer(questionId, value) {
    answers[questionId] = value;
    loadQuestion(currentQuestion);
}

function updateNextButton() {
    const question = questions[currentQuestion];
    const nextButton = document.getElementById('next-button');
    const isAnswered = answers[question.id] !== undefined;

    nextButton.disabled = !isAnswered;

    if (currentQuestion === questions.length - 1) {
        nextButton.textContent = '결과 분석 →';
    } else {
        nextButton.textContent = '다음 →';
    }
}

function previousQuestion() {
    if (currentQuestion > 0) {
        loadQuestion(currentQuestion - 1);
    }
}

function nextQuestion() {
    if (currentQuestion < questions.length - 1) {
        loadQuestion(currentQuestion + 1);
    } else {
        showResults();
    }
}

function showResults() {
    currentStep = 'result';
    document.getElementById('survey-screen').classList.add('hidden');
    document.getElementById('result-screen').classList.remove('hidden');

    const scores = calculateScores();
    const profile = getProfile(parseFloat(scores.anxiety.raw), parseFloat(scores.wtc.raw));

    renderResults(scores, profile);
}

// 점수 계산
function calculateScores() {
    const anxietyQuestions = questions.filter(q => q.category === 'anxiety');
    const wtcQuestions = questions.filter(q => q.category === 'wtc');

    // Anxiety 점수 계산
    let anxietySum = 0;
    let anxietyWeightSum = 0;
    anxietyQuestions.forEach(q => {
        const answer = answers[q.id] || 3;
        const score = q.reverse ? (6 - answer) : answer;
        anxietySum += score * q.weight;
        anxietyWeightSum += q.weight;
    });
    const anxietyRaw = anxietySum / anxietyWeightSum;

    // WTC 점수 계산
    let wtcSum = 0;
    let wtcWeightSum = 0;
    wtcQuestions.forEach(q => {
        const answer = answers[q.id] || 3;
        const score = q.reverse ? (6 - answer) : answer;
        wtcSum += score * q.weight;
        wtcWeightSum += q.weight;
    });
    const wtcRaw = wtcSum / wtcWeightSum;

    // 학년별 규준 기반 표준점수 계산
    const norms = gradeNorms[studentInfo.grade] || gradeNorms['중2'];

    const anxietyZ = (anxietyRaw - norms.anxiety.mean) / norms.anxiety.sd;
    const anxietyT = 50 + (anxietyZ * 10);
    const anxietyPercentile = calculatePercentile(anxietyZ);

    const wtcZ = (wtcRaw - norms.wtc.mean) / norms.wtc.sd;
    const wtcT = 50 + (wtcZ * 10);
    const wtcPercentile = calculatePercentile(wtcZ);

    // 하위 영역 분석
    const subScores = calculateSubScores();

    return {
        anxiety: {
            raw: anxietyRaw.toFixed(2),
            tScore: Math.round(anxietyT),
            percentile: anxietyPercentile,
            level: getLevel(anxietyT),
            description: getAnxietyDescription(anxietyT)
        },
        wtc: {
            raw: wtcRaw.toFixed(2),
            tScore: Math.round(wtcT),
            percentile: wtcPercentile,
            level: getLevel(wtcT),
            description: getWtcDescription(wtcT)
        },
        subScores: subScores,
        completionTime: Math.round((Date.now() - startTime) / 1000),
        totalQuestions: questions.length,
        grade: studentInfo.grade,
        name: studentInfo.name
    };
}

function calculateSubScores() {
    const subScores = {};

    // 각 하위 카테고리별 점수 계산
    ['anxiety', 'wtc'].forEach(mainCategory => {
        const categoryQuestions = questions.filter(q => q.category === mainCategory);
        const subCategories = [...new Set(categoryQuestions.map(q => q.subCategory))];

        subCategories.forEach(subCat => {
            const subQuestions = categoryQuestions.filter(q => q.subCategory === subCat);
            let sum = 0;
            subQuestions.forEach(q => {
                const answer = answers[q.id] || 3;
                const score = q.reverse ? (6 - answer) : answer;
                sum += score;
            });
            const avg = sum / subQuestions.length;
            subScores[`${mainCategory}_${subCat}`] = avg.toFixed(2);
        });
    });

    return subScores;
}

function calculatePercentile(zScore) {
    // 누적 정규분포 근사
    const t = 1 / (1 + 0.2316419 * Math.abs(zScore));
    const d = 0.3989423 * Math.exp(-zScore * zScore / 2);
    const probability = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));

    let percentile;
    if (zScore >= 0) {
        percentile = (1 - probability) * 100;
    } else {
        percentile = probability * 100;
    }

    return Math.round(Math.max(1, Math.min(99, percentile)));
}

function getLevel(tScore) {
    if (tScore >= 65) return '매우 높음';
    if (tScore >= 55) return '높음';
    if (tScore >= 45) return '보통';
    if (tScore >= 35) return '낮음';
    return '매우 낮음';
}

function getAnxietyDescription(tScore) {
    if (tScore >= 65) return '영어 사용 상황에서 매우 높은 불안을 경험합니다. 전문적인 지원이 도움이 될 수 있습니다.';
    if (tScore >= 55) return '영어 사용 시 높은 불안감을 느낍니다. 체계적인 불안 완화 전략이 필요합니다.';
    if (tScore >= 45) return '또래 수준의 불안감을 보입니다. 작은 성공 경험을 쌓아가면 좋습니다.';
    if (tScore >= 35) return '영어 사용에 대한 불안이 낮은 편입니다. 긍정적인 학습 태도를 유지하세요.';
    return '영어 사용 상황에서 매우 편안함을 느낍니다. 훌륭한 정서적 기반을 가지고 있습니다.';
}

function getWtcDescription(tScore) {
    if (tScore >= 65) return '영어로 소통하려는 의지가 매우 높습니다. 이 강점을 계속 발전시키세요.';
    if (tScore >= 55) return '영어 의사소통에 적극적입니다. 다양한 실전 기회를 활용하세요.';
    if (tScore >= 45) return '또래 수준의 의사소통 의지를 보입니다. 점진적으로 참여를 늘려보세요.';
    if (tScore >= 35) return '영어 소통 의지가 낮은 편입니다. 흥미로운 주제로 시작해보세요.';
    return '영어 의사소통을 많이 꺼립니다. 안전한 환경에서 작은 시도부터 시작하세요.';
}

function getProfile(anxietyScore, wtcScore) {
    // 8가지 프로필 유형
    if (anxietyScore <= 2.5 && wtcScore >= 4.0) {
        return {
            type: '자신감 넘치는 의사소통가',
            emoji: '🌟',
            color: 'emerald',
            description: '불안감이 낮고 적극적으로 영어로 소통하려는 의지가 높습니다.',
            strengths: ['높은 자신감', '적극적 참여', '두려움 없는 도전'],
            challenges: ['실수를 통한 학습 기회 인식', '세밀한 정확성 향상'],
            recommendations: [
                '영어 토론, 프레젠테이션 등 고급 활동에 도전하세요',
                '리더십 역할을 맡아 다른 학생들을 도와주세요',
                '국제 교류 프로그램이나 경연대회에 참가해보세요'
            ]
        };
    } else if (anxietyScore <= 2.5 && wtcScore >= 3.0) {
        return {
            type: '편안한 학습자',
            emoji: '😊',
            color: 'blue',
            description: '불안감은 낮으나 의사소통 의지가 중간 수준입니다.',
            strengths: ['정서적 안정', '스트레스 관리 능력', '차분한 학습'],
            challenges: ['적극성 향상', '참여 빈도 증가'],
            recommendations: [
                '관심 주제로 영어 활동을 시작해보세요',
                '소규모 그룹 활동에서 점차 역할을 늘려가세요',
                '영어 사용의 즐거움과 실용성을 경험해보세요'
            ]
        };
    } else if (anxietyScore <= 2.5 && wtcScore < 3.0) {
        return {
            type: '잠재력 보유자',
            emoji: '🌱',
            color: 'teal',
            description: '불안감은 낮지만 의사소통 의지가 낮은 편입니다.',
            strengths: ['낮은 불안감', '잠재적 자신감', '안정적 학습 가능'],
            challenges: ['동기 부여', '참여 의지 향상', '흥미 발견'],
            recommendations: [
                '흥미로운 주제(게임, 음악, 영화 등)로 영어에 접근하세요',
                '작은 성공 경험을 통해 동기를 키워보세요',
                '영어 사용의 실용적 가치를 경험해보세요'
            ]
        };
    } else if (anxietyScore <= 3.5 && wtcScore >= 4.0) {
        return {
            type: '용감한 도전자',
            emoji: '💪',
            color: 'orange',
            description: '불안감이 있지만 적극적으로 소통하려는 의지가 높습니다.',
            strengths: ['높은 의지력', '도전 정신', '끈기'],
            challenges: ['불안 관리', '자신감 구축', '실수 두려움 극복'],
            recommendations: [
                '작은 성공을 축하하며 자신감을 쌓으세요',
                '실수는 배움의 기회임을 기억하세요',
                '편안한 환경에서 연습량을 늘려가세요',
                '이완 기법을 배워 불안을 관리하세요'
            ]
        };
    } else if (anxietyScore <= 3.5 && wtcScore >= 3.0) {
        return {
            type: '균형잡힌 학습자',
            emoji: '⚖️',
            color: 'indigo',
            description: '불안과 의사소통 의지가 모두 중간 수준입니다.',
            strengths: ['균형 잡힌 태도', '점진적 발전 가능', '적응력'],
            challenges: ['불안 완화', '참여도 향상', '동기 강화'],
            recommendations: [
                '체계적인 연습으로 자신감을 쌓으세요',
                '편안한 소그룹 활동부터 시작하세요',
                '성공 경험을 통해 불안을 줄여가세요',
                '목표를 세워 꾸준히 실천하세요'
            ]
        };
    } else if (anxietyScore <= 3.5 && wtcScore < 3.0) {
        return {
            type: '조심스러운 관찰자',
            emoji: '🤔',
            color: 'slate',
            description: '중간 수준의 불안과 낮은 의사소통 의지를 보입니다.',
            strengths: ['신중함', '관찰력', '사려깊음'],
            challenges: ['불안 관리', '참여 의지', '자신감 부족'],
            recommendations: [
                '안전하고 편안한 환경에서 시작하세요',
                '일대일 상황에서 점차 연습해보세요',
                '흥미있는 주제로 동기를 찾아보세요',
                '작은 목표를 달성하며 자신감을 쌓으세요'
            ]
        };
    } else if (anxietyScore > 3.5 && wtcScore >= 3.5) {
        return {
            type: '열정적 노력가',
            emoji: '🔥',
            color: 'rose',
            description: '높은 불안에도 불구하고 소통 의지를 유지하고 있습니다.',
            strengths: ['강한 의지', '끈기', '노력'],
            challenges: ['높은 불안', '스트레스 관리', '자신감 부족'],
            recommendations: [
                '불안 관리가 최우선입니다. 전문가 상담을 고려하세요',
                '자신의 노력과 용기를 인정해주세요',
                '무리하지 말고 편안한 속도로 진행하세요',
                '이완 기법과 긍정적 자기대화를 연습하세요'
            ]
        };
    } else {
        return {
            type: '지원이 필요한 학습자',
            emoji: '🤝',
            color: 'red',
            description: '높은 불안과 낮은 의사소통 의지를 보입니다.',
            strengths: ['개선 가능성', '잠재력', '발전 기회'],
            challenges: ['높은 불안', '낮은 의지', '부정적 경험'],
            recommendations: [
                '전문적인 지원과 상담이 필요합니다',
                '매우 안전하고 지지적인 환경에서 시작하세요',
                '영어에 대한 긍정적 경험을 만들어가세요',
                '작은 성공부터 차근차근 쌓아가세요',
                '학부모, 교사와 협력하여 개별화된 접근이 필요합니다'
            ]
        };
    }
}

function renderResults(scores, profile) {
    // 학생 정보
    document.getElementById('result-student-name').textContent = scores.name;
    document.getElementById('result-student-grade').textContent = scores.grade;

    // 프로필 카드
    document.getElementById('profile-emoji').textContent = profile.emoji;
    document.getElementById('profile-type').textContent = profile.type;
    document.getElementById('profile-description').textContent = profile.description;

    // 프로필 색상 적용
    const profileCard = document.getElementById('profile-card');
    profileCard.className = `bg-gradient-to-br from-${profile.color}-50 to-${profile.color}-100 p-6 rounded-2xl border-2 border-${profile.color}-200 shadow-lg`;

    // 점수 표시
    renderScoreCard('anxiety', scores.anxiety);
    renderScoreCard('wtc', scores.wtc);

    // 강점
    const strengthsList = document.getElementById('strengths-list');
    strengthsList.innerHTML = '';
    profile.strengths.forEach(strength => {
        const li = document.createElement('li');
        li.className = 'flex items-start gap-2';
        li.innerHTML = `<span class="text-emerald-500 mt-1">✓</span><span>${strength}</span>`;
        strengthsList.appendChild(li);
    });

    // 도전과제
    const challengesList = document.getElementById('challenges-list');
    challengesList.innerHTML = '';
    profile.challenges.forEach(challenge => {
        const li = document.createElement('li');
        li.className = 'flex items-start gap-2';
        li.innerHTML = `<span class="text-amber-500 mt-1">⚠</span><span>${challenge}</span>`;
        challengesList.appendChild(li);
    });

    // 맞춤 제안
    const recommendationsList = document.getElementById('recommendations-list');
    recommendationsList.innerHTML = '';
    profile.recommendations.forEach((rec, index) => {
        const li = document.createElement('li');
        li.className = 'flex items-start gap-3 p-4 bg-indigo-50 rounded-xl';
        li.innerHTML = `<span class="flex-shrink-0 w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-sm font-bold">${index + 1}</span><span class="text-gray-700">${rec}</span>`;
        recommendationsList.appendChild(li);
    });

    // 하위 영역 분석
    renderSubScores(scores.subScores);

    // 완료 시간
    const minutes = Math.floor(scores.completionTime / 60);
    const seconds = scores.completionTime % 60;
    document.getElementById('completion-time').textContent = `${minutes}분 ${seconds}초`;
}

function renderScoreCard(type, scoreData) {
    const container = document.getElementById(`${type}-score-card`);

    const title = type === 'anxiety' ? '영어 불안도' : '의사소통 의지';
    const icon = type === 'anxiety' ? '😰' : '🗣️';
    const colorClass = type === 'anxiety' ? 'rose' : 'emerald';

    container.innerHTML = `
        <div class="bg-white p-6 rounded-2xl border-2 border-gray-200 shadow-md">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-xl font-bold text-gray-800">${icon} ${title}</h3>
                <span class="px-3 py-1 bg-${colorClass}-100 text-${colorClass}-700 rounded-full text-sm font-semibold">${scoreData.level}</span>
            </div>

            <div class="space-y-3">
                <div>
                    <div class="flex justify-between mb-1">
                        <span class="text-sm text-gray-600">원점수</span>
                        <span class="font-bold text-gray-800">${scoreData.raw}</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-3">
                        <div class="bg-${colorClass}-500 h-3 rounded-full transition-all duration-500" style="width: ${(scoreData.raw / 5) * 100}%"></div>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4 pt-3 border-t border-gray-200">
                    <div class="text-center">
                        <div class="text-2xl font-bold text-${colorClass}-600">${scoreData.tScore}</div>
                        <div class="text-xs text-gray-500">T점수</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-${colorClass}-600">${scoreData.percentile}%</div>
                        <div class="text-xs text-gray-500">백분위</div>
                    </div>
                </div>

                <p class="text-sm text-gray-700 pt-3 border-t border-gray-200">${scoreData.description}</p>
            </div>
        </div>
    `;
}

function renderSubScores(subScores) {
    const container = document.getElementById('subscores-container');
    container.innerHTML = '';

    for (const [key, value] of Object.entries(subScores)) {
        const label = subCategoryLabels[key];
        const score = parseFloat(value);
        const percentage = (score / 5) * 100;

        const category = key.split('_')[0];
        const colorClass = category === 'anxiety' ? 'rose' : 'emerald';

        const div = document.createElement('div');
        div.className = 'bg-gray-50 p-4 rounded-xl';
        div.innerHTML = `
            <div class="flex justify-between mb-2">
                <span class="text-sm font-medium text-gray-700">${label}</span>
                <span class="text-sm font-bold text-gray-800">${value}</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
                <div class="bg-${colorClass}-500 h-2 rounded-full transition-all duration-500" style="width: ${percentage}%"></div>
            </div>
        `;
        container.appendChild(div);
    }
}

function downloadPDF() {
    alert('PDF 다운로드 기능은 개발 중입니다.');
}

function restartAssessment() {
    currentStep = 'intro';
    studentInfo = { name: '', grade: '' };
    answers = {};
    currentQuestion = 0;

    document.getElementById('result-screen').classList.add('hidden');
    document.getElementById('intro-screen').classList.remove('hidden');

    document.getElementById('student-name').value = '';
    document.getElementById('student-grade').value = '';
    document.getElementById('start-button').disabled = true;
}