// v4.0 Global State
let currentStep = 'intro'; // 'intro', 'survey', 'result'
let answers = {};
let currentQuestionIndex = 0;
let studentInfo = { name: '', grade: '' };
let resultType = 'C'; // Default to Type C
let resultProfile = null; // Stores the detailed STEAM assessment result

// --- Core Functions ---

document.addEventListener('DOMContentLoaded', () => {
    console.log('Assessment app loaded successfully');
    console.log('startSurvey function:', typeof startSurvey);
});

window.startSurvey = function() {
    console.log('startSurvey called');
    try {
        currentStep = 'survey';
        const introScreen = document.getElementById('intro-screen');
        const surveyScreen = document.getElementById('survey-screen');

        console.log('intro-screen element:', introScreen);
        console.log('survey-screen element:', surveyScreen);

        if (!introScreen || !surveyScreen) {
            console.error('Required screen elements not found');
            return;
        }

        introScreen.classList.add('hidden');
        surveyScreen.classList.remove('hidden');
        loadQuestion(0);
    } catch (error) {
        console.error('Error in startSurvey:', error);
        alert('진단을 시작하는 중 오류가 발생했습니다. 페이지를 새로고침해주세요.');
    }
}

function loadQuestion(index) {
    currentQuestionIndex = index;
    const question = questions[index];

    // Update Progress
    const progress = ((index + 1) / questions.length) * 100;
    document.getElementById('current-question-num').textContent = index + 1;
    document.getElementById('progress-bar').style.width = `${progress}%`;
    document.getElementById('progress-percent').textContent = Math.round(progress);

    // Update Question Text
    document.getElementById('question-situation').textContent = question.situation;
    document.getElementById('question-text').textContent = question.text;

    // Render Answer Options
    const optionsContainer = document.getElementById('answer-options');
    optionsContainer.innerHTML = '';
    const optionEntries = Object.entries(question.options).sort((a, b) => b[0] - a[0]);

    optionEntries.forEach(([value, label], index) => {
        const numValue = parseInt(value);
        const isSelected = answers[question.id] === numValue;

        const button = document.createElement('button');
        const gradientColors = {
            5: 'from-green-50 to-emerald-50 border-green-300 hover:border-green-400 hover:shadow-green-200',
            4: 'from-blue-50 to-cyan-50 border-blue-300 hover:border-blue-400 hover:shadow-blue-200',
            3: 'from-yellow-50 to-amber-50 border-yellow-300 hover:border-yellow-400 hover:shadow-yellow-200',
            2: 'from-orange-50 to-red-50 border-orange-300 hover:border-orange-400 hover:shadow-orange-200',
            1: 'from-red-50 to-pink-50 border-red-300 hover:border-red-400 hover:shadow-red-200'
        };

        const baseClasses = isSelected
            ? 'border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-lg scale-[1.02] ring-2 ring-indigo-200'
            : `bg-gradient-to-r ${gradientColors[numValue]} border-2 hover:shadow-md hover:scale-[1.01]`;

        button.className = `w-full p-5 rounded-2xl text-left transition-all duration-300 transform ${baseClasses}`;
        button.onclick = () => selectAnswer(question.id, numValue);
        button.style.animationDelay = `${index * 50}ms`;
        button.classList.add('animate-slideInUp');

        const emojiMap = { 5: '🤩', 4: '🙂', 3: '🤔', 2: '😕', 1: '😥' };
        const scoreText = { 5: '매우 그렇다', 4: '그렇다', 3: '보통', 2: '아니다', 1: '전혀 아니다' };

        button.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="text-4xl transform transition-transform duration-300 ${isSelected ? 'scale-125' : 'group-hover:scale-110'}">${emojiMap[numValue]}</div>
                <div class="flex-1">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-bold px-2 py-0.5 rounded-full ${isSelected ? 'bg-indigo-200 text-indigo-800' : 'bg-gray-200 text-gray-600'}">${scoreText[numValue]}</span>
                    </div>
                    <span class="font-semibold text-gray-800 text-base leading-relaxed block">${label}</span>
                </div>
                ${isSelected ? `<div class="w-7 h-7 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0 shadow-md animate-scaleIn"><svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg></div>` : ''}
            </div>
        `;
        optionsContainer.appendChild(button);
    });

    // Update Navigation
    document.getElementById('prev-button').disabled = (index === 0);
    updateNextButton();
}

function selectAnswer(questionId, value) {
    answers[questionId] = value;
    // Automatically move to next question for better UX
    setTimeout(() => {
        if (currentQuestionIndex < questions.length - 1) {
            loadQuestion(currentQuestionIndex + 1);
        } else {
            // If it's the last question, enable the result button
            updateNextButton();
        }
    }, 200);
}


function updateNextButton() {
    const nextButton = document.getElementById('next-button');
    const isLastQuestion = currentQuestionIndex === questions.length - 1;
    const isAnswered = answers[questions[currentQuestionIndex].id] !== undefined;
    
    nextButton.disabled = !isAnswered;
    
    if (isLastQuestion) {
        nextButton.textContent = '결과 분석하기 →';
    } else {
        nextButton.textContent = '다음 →';
    }
}

window.previousQuestion = function() {
    if (currentQuestionIndex > 0) {
        loadQuestion(currentQuestionIndex - 1);
    }
}

window.nextQuestion = function() {
    if (currentQuestionIndex < questions.length - 1) {
        loadQuestion(currentQuestionIndex + 1);
    } else {
        showResults();
    }
}

function showResults() {
    currentStep = 'result';
    document.getElementById('survey-screen').classList.add('hidden');
    document.getElementById('result-screen').classList.remove('hidden');

    const scores = calculateScores();
    resultProfile = getLearningProfile(scores); // Assign to global resultProfile
    renderResults(resultProfile);
}

// --- Calculation and Rendering Logic ---

function calculateScores() {
    const scores = {
        logical: 0,
        creative: 0,
        inquiry: 0,
        resilience: 0,
        expression: 0
    };
    const counts = { // To keep track of how many questions contributed to each category
        logical: 0,
        creative: 0,
        inquiry: 0,
        resilience: 0,
        expression: 0
    };

    questions.forEach(q => {
        const answer = answers[q.id] || 3; // Default to 3 if not answered
        if (scores.hasOwnProperty(q.category)) {
            scores[q.category] += answer * (q.weight || 1);
            counts[q.category] += (q.weight || 1);
        }
    });

    // Calculate average scores
    for (const key in scores) {
        if (counts[key] > 0) {
            scores[key] = parseFloat((scores[key] / counts[key]).toFixed(1)); // Round to one decimal place
        } else {
            scores[key] = 0; // If no questions for a category, score is 0
        }
    }
    return scores;
}

function getLearningProfile(scores) {
    const profile = {
        personaTitle: "균형잡힌 성장가",
        overallSummary: "우리 아이는 모든 역량에서 고른 발달을 보이며, 어떤 분야로든 성장할 수 있는 잠재력을 지니고 있습니다. 지속적인 격려와 다양한 경험을 통해 자신만의 강점을 발견하고 발전시켜 나갈 것입니다.",
        categoryScores: [],
        strengths: [],
        areasForGrowth: []
    };

    const categories = [
        { key: 'logical', name: '논리분석력' },
        { key: 'creative', name: '창의직관력' },
        { key: 'inquiry', name: '지적탐구심' },
        { key: 'resilience', name: '학습회복력' },
        { key: 'expression', name: '표현력' },
    ];

    let highestScore = -1, lowestScore = 6;
    let highestCat = '', lowestCat = '';

    // 1. Build detailed category scores and find highest/lowest
    categories.forEach(category => {
        const score = scores[category.key];
        let level;
        if (score >= 4.0) {
            level = 'high';
        } else if (score >= 3.0) {
            level = 'mid';
        } else {
            level = 'low';
        }

        profile.categoryScores.push({
            category: category.name,
            score: score,
            level: level,
            description: learningProfiles[category.key][level]
        });

        if (score > highestScore) {
            highestScore = score;
            highestCat = category.key;
        }
        if (score < lowestScore) {
            lowestScore = score;
            lowestCat = category.key;
        }

        // Add to strengths or areasForGrowth based on level
        if (level === 'high') {
            profile.strengths.push({
                category: category.name,
                recommendation: recommendations[category.key]
            });
        } else if (level === 'low') {
            profile.areasForGrowth.push({
                category: category.name,
                recommendation: recommendations[category.key]
            });
        }
    });

    // 2. Generate persona-based summary if there's a clear distinction
    const scoreSpread = highestScore - lowestScore;

    if (scoreSpread >= 1.5 && highestCat !== lowestCat) {
        const personas = {
            'logical': {
                'creative': { title: '차가운 머리의 발명가', summary: '논리력과 창의력의 간극은, 아이디어를 현실로 구현하는 과정에서의 어려움을 의미할 수 있습니다. 상상한 것을 체계적으로 만들어내는 경험을 통해 두 강점을 연결해주세요.' },
                'inquiry': { title: '사실 기반의 분석가', summary: '강한 논리력에 비해 탐구심이 부족한 것은, 아는 것을 깊게 파고들기보다 활용하는 데 더 관심이 많다는 의미입니다. "왜 그럴까?"라는 질문을 통해 지적 호기심을 자극해주세요.' },
                'resilience': { title: '계산적인 전략가', summary: '논리적으로 완벽함을 추구하기에, 실패 가능성이 있는 도전을 회피할 수 있습니다. 결과보다 과정을 칭찬하며, 실패가 또 다른 학습임을 알려주는 것이 중요합니다.' },
                'expression': { title: '과묵한 문제 해결사', summary: '뛰어난 논리력에 비해 표현력이 부족한 것은, 머릿속의 복잡한 생각을 말로 풀어내는 것을 어려워한다는 의미입니다. 그림이나 글 등 다른 표현 방법을 제안해보세요.' }
            },
            'creative': {
                'logical': { title: '자유로운 영혼의 예술가', summary: '뛰어난 창의력에 비해 논리력이 부족한 것은, 아이디어를 구체적인 결과물로 만드는 데 어려움을 겪을 수 있음을 의미합니다. 생각의 지도를 그려보거나, 단계별 계획을 세우는 연습이 도움이 됩니다.' },
                'inquiry': { title: '몽상가', summary: '창의력은 풍부하지만, 현실 세계에 대한 탐구심이 부족하여 상상이 공상에만 머무를 수 있습니다. 아이의 상상을 현실과 연결하는 질문을 던져주세요. (예: "이런 비행기가 진짜 날려면 어떤 날개가 필요할까?")' },
                'resilience': { title: '섬세한 감성의 예술가', summary: '창의적인 아이들은 자신의 아이디어가 비판받는 것에 민감할 수 있습니다. "정답은 없어"라는 말로 아이의 독창성을 지지해주고, 작은 시도 자체를 칭찬해주세요.' },
                'expression': { title: '행동으로 보여주는 창작자', summary: '풍부한 창의력에 비해 표현력이 부족한 것은, 말보다는 행동이나 결과물로 자신을 보여주는 것을 선호하기 때문일 수 있습니다. 아이의 작품에 대해 부모님이 대신 이야기해주며 언어적 표현 모델을 보여주세요.' }
            },
            'inquiry': {
                'logical': { title: '호기심 많은 관찰자', summary: '지적 호기심은 왕성하지만, 그것을 논리적으로 분석하고 정리하는 데 어려움을 느낄 수 있습니다. 관찰일지를 쓰거나, 탐구 주제를 마인드맵으로 정리하는 활동이 도움이 됩니다.' },
                'creative': { title: '사실 탐구에 집중하는 학자', summary: '호기심이 사실과 지식에 집중되어 있어, 상상력을 발휘하는 데에는 흥미가 적을 수 있습니다. 탐구한 사실을 바탕으로 "만약에?"라는 상상 질문을 던져보세요.' },
                'resilience': { title: '쉽게 지치는 탐험가', summary: '새로운 것에 대한 호기심은 강하지만, 어려움에 부딪히면 쉽게 흥미를 잃을 수 있습니다. 탐구의 목표를 작게 나누어, 작은 성공의 경험을 자주 만들어주는 것이 중요합니다.' },
                'expression': { title: '지식을 쌓아두는 수집가', summary: '방대한 지식을 가지고 있지만, 그것을 다른 사람에게 설명하고 공유하는 데에는 소극적일 수 있습니다. 아이가 '선생님'이 되어 부모님을 가르쳐주는 놀이를 통해 표현의 즐거움을 알려주세요.' }
            },
            'resilience': {
                'logical': { title: '무모한 도전자', summary: '실패를 두려워하지 않고 일단 부딪히고 보지만, 실패의 원인을 논리적으로 분석하여 배우는 점은 부족할 수 있습니다. "이번엔 왜 안됐을까?"라는 질문을 통해 실패를 학습의 기회로 만들도록 도와주세요.' },
                'creative': { title: '성실한 모방가', summary: '끈기 있게 문제를 해결하지만, 새로운 방법을 시도하기보다는 검증된 방법을 고수하려는 경향이 있습니다. "다른 방법은 없을까?"라는 질문으로 창의적 문제 해결을 유도해주세요.' },
                'inquiry': { title: '목표 지향적 실행가', summary: '주어진 과제는 끈기 있게 해결하지만, 과제 자체에 대한 근원적인 호기심은 부족할 수 있습니다. 과제와 관련된 재미있는 배경 지식을 이야기해주어 지적 탐구심을 자극해주세요.' },
                'expression': { title: '우직한 행동가', summary: '말보다는 행동으로 끈기 있게 보여주는 유형입니다. 자신의 노력과 성과를 말로 표현하는 경험이 부족할 수 있습니다. 아이가 노력한 과정을 부모님이 언어로 인정하고 칭찬해주세요.' }
            },
            'expression': {
                'logical': { title: '공감 능력이 뛰어난 이야기꾼', summary: '논리적인 근거보다는, 감성적인 언어와 풍부한 표정으로 사람들의 마음을 움직이는 데 강점을 보입니다. 자신의 주장에 '왜냐하면'을 붙여 근거를 대는 연습을 통해 논리적 설득력을 강화할 수 있습니다.' },
                'creative': { title: '아이디어를 공유하는 리더', summary: '자신의 생각을 표현하는 데는 강하지만, 완전히 새로운 아이디어를 내는 데에는 흥미가 적을 수 있습니다. 당연하게 여겼던 것들에 대해 "정말 그럴까?"라는 질문을 던져 비판적 사고를 자극해주세요.' },
                'inquiry': { title: '아는 것을 나누는 선생님', summary: '자신이 아는 것을 다른 사람에게 가르쳐주며 더 깊이 배우는 유형입니다. 새로운 지식에 대한 탐구심이 부족하게 느껴진다면, 아이가 좋아하는 분야의 심화 지식을 접할 기회를 만들어주세요.' },
                'resilience': { title: '말로 해결하려는 협상가', summary: '어려운 문제에 부딪혔을 때, 직접 해결하기보다 뛰어난 언변으로 도움을 요청하거나 상황을 유리하게 만드는 데 능숙할 수 있습니다. 스스로 끝까지 해결해내는 경험의 중요성을 알려주는 것이 필요합니다.' }
            }
        };

        if (personas[highestCat] && personas[highestCat][lowestCat]) {
            const persona = personas[highestCat][lowestCat];
            profile.personaTitle = persona.title;
            profile.overallSummary = persona.summary;
        }
    }

    return profile;
}



function renderResults(resultProfile) {
    const resultContent = document.getElementById('result-content');

    let categoryDetailsHtml = resultProfile.categoryScores.map(cat => `
        <div class="bg-gray-50 p-4 rounded-xl border border-gray-200 flex items-center justify-between">
            <span class="font-semibold text-gray-700">${
                cat.category === 'logical' ? '논리분석력' :
                cat.category === 'creative' ? '창의직관력' :
                cat.category === 'inquiry' ? '지적탐구심' :
                cat.category === 'resilience' ? '학습회복력' :
                cat.category === 'expression' ? '표현력' : cat.category
            }</span>
            <div class="flex items-center gap-2">
                <span class="text-indigo-600 font-bold text-lg">${cat.score.toFixed(1)}점</span>
                <span class="text-sm text-gray-500">(${
                    cat.level === 'high' ? '높음' :
                    cat.level === 'mid' ? '보통' : '낮음'
                })</span>
            </div>
        </div>
        <p class="text-sm text-gray-600 mt-2 mb-4">${cat.description}</p>
    `).join('');

    let strengthsHtml = resultProfile.strengths.map(s => `
        <li class="flex items-start gap-3 p-4 bg-indigo-50 rounded-xl">
            <span class="text-2xl mt-1">💪</span>
            <div>
                <span class="font-semibold text-gray-800">${
                    s.category === 'logical' ? '논리분석력' :
                    s.category === 'creative' ? '창의직관력' :
                    s.category === 'inquiry' ? '지적탐구심' :
                    s.category === 'resilience' ? '학습회복력' :
                    s.category === 'expression' ? '표현력' : s.category
                }</span>
                <p class="text-gray-700 text-sm mt-1">${s.recommendation}</p>
            </div>
        </li>
    `).join('');

    if (resultProfile.strengths.length === 0) {
        strengthsHtml = `<p class="text-center text-gray-500">특별히 뛰어난 강점은 없지만, 모든 영역에서 고른 잠재력을 보입니다.</p>`;
    }

    let areasForGrowthHtml = resultProfile.areasForGrowth.map(a => `
        <li class="flex items-start gap-3 p-4 bg-red-50 rounded-xl">
            <span class="text-2xl mt-1">🌱</span>
            <div>
                <span class="font-semibold text-gray-800">${
                    a.category === 'logical' ? '논리분석력' :
                    a.category === 'creative' ? '창의직관력' :
                    a.category === 'inquiry' ? '지적탐구심' :
                    a.category === 'resilience' ? '학습회복력' :
                    a.category === 'expression' ? '표현력' : a.category
                }</span>
                <p class="text-gray-700 text-sm mt-1">${a.recommendation}</p>
            </div>
        </li>
    `).join('');

    if (resultProfile.areasForGrowth.length === 0) {
        areasForGrowthHtml = `<p class="text-center text-gray-500">모든 영역에서 고른 발달을 보이며, 특별히 보완이 필요한 영역은 없습니다.</p>`;
    }

    resultContent.innerHTML = `
        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn text-center">
            <h2 class="text-2xl font-semibold text-gray-500 mb-2">우리 아이의 학습 페르소나</h2>
            <p class="text-5xl font-extrabold text-indigo-600 mb-4">${resultProfile.personaTitle}</p>
            <p class="text-lg text-gray-700 leading-relaxed">${resultProfile.overallSummary}</p>
        </div>

        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn">
            <h3 class="text-2xl font-bold text-gray-800 mb-6 text-center">💡 영역별 상세 분석</h3>
            <div class="space-y-4">
                ${categoryDetailsHtml}
            </div>
        </div>

        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn">
            <h3 class="text-2xl font-bold text-gray-800 mb-6 text-center">🌟 주요 강점 및 맞춤 전략</h3>
            <ul class="space-y-4">
                ${strengthsHtml}
            </ul>
        </div>

        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn">
            <h3 class="text-2xl font-bold text-gray-800 mb-6 text-center">📈 성장을 위한 조언</h3>
            <ul class="space-y-4">
                ${areasForGrowthHtml}
            </ul>
        </div>
        
        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn">
            <h3 class="text-2xl font-bold text-gray-800 mb-2 text-center">상담을 통해 더 자세한 로드맵을 받아보세요!</h3>
            <p class="text-center text-gray-500 mb-6">아래 정보를 입력하고 [결과 복사] 버튼을 눌러 카카오톡으로 보내주세요.</p>
            
            <div class="grid md:grid-cols-2 gap-4 mb-6">
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">아이 이름</label>
                    <input type="text" id="student-name-result" class="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:ring-2 focus:ring-indigo-500" placeholder="김오픈">
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">성별</label>
                    <select id="student-gender-result" class="w-full px-4 py-3 rounded-xl border-2 border-gray-200 bg-white focus:ring-2 focus:ring-indigo-500">
                        <option value="">선택</option>
                        <option value="남">남</option>
                        <option value="여">여</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">학년</label>
                    <select id="student-grade-result" class="w-full px-4 py-3 rounded-xl border-2 border-gray-200 bg-white focus:ring-2 focus:ring-indigo-500">
                        <option value="">학년 선택</option>
                        <option value="유아">유아</option>
                        <option value="초1">초1</option>
                        <option value="초2">초2</option>
                        <option value="초3">초3</option>
                        <option value="초4">초4</option>
                        <option value="초5">초5</option>
                        <option value="초6">초6</option>
                        <option value="중1">중1</option>
                        <option value="중2">중2</option>
                        <option value="중3">중3</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-2">지역</label>
                    <input type="text" id="student-region-result" class="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:ring-2 focus:ring-indigo-500" placeholder="예: 강남구, 분당구">
                </div>
                <div class="md:col-span-2">
                    <label class="block text-sm font-semibold text-gray-700 mb-2">선호 그룹핑</label>
                    <select id="student-grouping-result" class="w-full px-4 py-3 rounded-xl border-2 border-gray-200 bg-white focus:ring-2 focus:ring-indigo-500">
                        <option value="">선택</option>
                        <option value="1:1">1:1 개인 수업</option>
                        <option value="1:다수">1:다수 그룹 수업</option>
                    </select>
                </div>
            </div>

            <button id="copy-button" onclick="copyResults()" class="w-full py-4 bg-teal-500 text-white font-bold text-lg rounded-xl hover:bg-teal-600 transition shadow-lg">
                📋 카톡 상담용 결과 내용 복사
            </button>
            <p class="text-center text-sm text-gray-500 mt-3">복사된 내용을 <strong>카카오톡 ID: openedu</strong> 로 보내주세요!</p>
        </div>

         <div class="text-center mt-6">
            <a href="javascript:restartAssessment()" class="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                ‹ 다시 검사하기
            </a>
        </div>
    `;
}

window.copyResults = function() {
    const nameInput = document.getElementById('student-name-result');
    const genderInput = document.getElementById('student-gender-result');
    const gradeInput = document.getElementById('student-grade-result');
    const regionInput = document.getElementById('student-region-result');
    const groupingInput = document.getElementById('student-grouping-result');
    const copyButton = document.getElementById('copy-button');

    if (!nameInput.value.trim() || !genderInput.value || !gradeInput.value || !regionInput.value.trim() || !groupingInput.value) {
        alert('모든 상담 정보를 입력해주세요. (이름, 성별, 학년, 지역, 선호 그룹핑)');
        nameInput.focus();
        return;
    }
    
    studentInfo.name = nameInput.value.trim();
    studentInfo.gender = genderInput.value;
    studentInfo.grade = gradeInput.value;
    studentInfo.region = regionInput.value.trim();
    studentInfo.grouping = groupingInput.value;

    if (!resultProfile) {
        alert('분석 결과가 없습니다. 다시 진단을 시작해주세요.');
        return;
    }

    let detailedResultText = `
[Open Edu 학습 성향 진단 결과]

* 문의 정보
- 이름: ${studentInfo.name}
- 성별: ${studentInfo.gender}
- 학년: ${studentInfo.grade}
- 지역: ${studentInfo.region}
- 선호 그룹핑: ${studentInfo.grouping}

* 우리 아이의 학습 페르소나: ${resultProfile.personaTitle}
${resultProfile.overallSummary}

* 영역별 상세 분석:
`;

    resultProfile.categoryScores.forEach(cat => {
        detailedResultText += `
- ${
            cat.category === 'logical' ? '논리분석력' :
            cat.category === 'creative' ? '창의직관력' :
            cat.category === 'inquiry' ? '지적탐구심' :
            cat.category === 'resilience' ? '학습회복력' :
            cat.category === 'expression' ? '표현력' : cat.category
        } (${cat.score.toFixed(1)}점, ${
            cat.level === 'high' ? '높음' :
            cat.level === 'mid' ? '보통' : '낮음'
        }): ${cat.description}
`;
    });

    if (resultProfile.strengths.length > 0) {
        detailedResultText += `
* 주요 강점 및 맞춤 전략:
`;
        resultProfile.strengths.forEach(s => {
            detailedResultText += `
- ${
                s.category === 'logical' ? '논리분석력' :
                s.category === 'creative' ? '창의직관력' :
                s.category === 'inquiry' ? '지적탐구심' :
                s.category === 'resilience' ? '학습회복력' :
                s.category === 'expression' ? '표현력' : s.category
            }: ${s.recommendation}
`;
        });
    }

    if (resultProfile.areasForGrowth.length > 0) {
        detailedResultText += `
* 성장을 위한 조언:
`;
        resultProfile.areasForGrowth.forEach(a => {
            detailedResultText += `
- ${
                a.category === 'logical' ? '논리분석력' :
                a.category === 'creative' ? '창의직관력' :
                a.category === 'inquiry' ? '지적탐구심' :
                a.category === 'resilience' ? '학습회복력' :
                a.category === 'expression' ? '표현력' : a.category
            }: ${a.recommendation}
`;
        });
    }
    
    detailedResultText += `

자세한 상담을 받고 싶습니다.
`.trim();

    navigator.clipboard.writeText(detailedResultText).then(() => {
        copyButton.textContent = '✅ 복사 완료!';
        copyButton.classList.remove('bg-teal-500', 'hover:bg-teal-600');
        copyButton.classList.add('bg-green-500');
        setTimeout(() => {
            copyButton.textContent = '📋 카톡 상담용 결과 내용 복사';
            copyButton.classList.remove('bg-green-500');
            copyButton.classList.add('bg-teal-500', 'hover:bg-teal-600');
        }, 2000);
    }).catch(err => {
        alert('결과 복사에 실패했습니다. 수동으로 복사해주세요.');
        console.error('Copy failed', err);
    });
}


window.restartAssessment = function() {
    currentStep = 'intro';
    answers = {};
    currentQuestionIndex = 0;
    studentInfo = { name: '', grade: '' };

    document.getElementById('result-screen').classList.add('hidden');
    document.getElementById('intro-screen').classList.remove('hidden');
}