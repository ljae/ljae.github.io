// v4.0 Global State
let currentStep = 'intro'; // 'intro', 'survey', 'result'
let answers = {};
let currentQuestionIndex = 0;
let studentInfo = { name: '', grade: '' };
let resultType = 'C'; // Default to Type C
let resultProfile = null; // Stores the detailed STEAM assessment result

// --- Core Functions ---

document.addEventListener('DOMContentLoaded', () => {
    // No validation needed on start anymore
});

function startSurvey() {
    currentStep = 'survey';
    document.getElementById('intro-screen').classList.add('hidden');
    document.getElementById('survey-screen').classList.remove('hidden');
    loadQuestion(0);
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

    optionEntries.forEach(([value, label]) => {
        const numValue = parseInt(value);
        const isSelected = answers[question.id] === numValue;

        const button = document.createElement('button');
        button.className = `w-full p-4 rounded-xl border-2 text-left transition-all duration-200 ${isSelected ? 'border-indigo-500 bg-indigo-50 shadow-md' : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'}`;
        button.onclick = () => selectAnswer(question.id, numValue);
        
        const emojiMap = { 5: '🤩', 4: '🙂', 3: '🤔', 2: '😕', 1: '😥' };
        
        button.innerHTML = `
            <div class="flex items-center gap-4">
                <span class="text-3xl">${emojiMap[numValue]}</span>
                <span class="flex-1 font-semibold text-gray-700">${label}</span>
                ${isSelected ? `<div class="w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center flex-shrink-0"><svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg></div>` : ''}
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

function previousQuestion() {
    if (currentQuestionIndex > 0) {
        loadQuestion(currentQuestionIndex - 1);
    }
}

function nextQuestion() {
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
        overallSummary: "",
        categoryScores: [],
        strengths: [],
        areasForGrowth: []
    };

    const categories = ['logical', 'creative', 'inquiry', 'resilience', 'expression'];
    const scoreLevels = {};

    // Determine level for each category and build categoryScores array
    categories.forEach(category => {
        const score = scores[category];
        let level;
        if (score >= 4.0) {
            level = 'high';
        } else if (score >= 3.0) {
            level = 'mid';
        } else {
            level = 'low';
        }
        scoreLevels[category] = level;

        profile.categoryScores.push({
            category: category,
            score: score,
            level: level,
            description: learningProfiles[category][level]
        });

        // Add to strengths or areasForGrowth based on level
        if (level === 'high') {
            profile.strengths.push({
                category: category,
                recommendation: recommendations[category]
            });
        } else if (level === 'low') {
            profile.areasForGrowth.push({
                category: category,
                recommendation: recommendations[category]
            });
        }
    });

    // Generate overall summary
    const highScores = profile.categoryScores.filter(c => c.level === 'high');
    const lowScores = profile.categoryScores.filter(c => c.level === 'low');

    if (highScores.length >= 3) {
        profile.overallSummary = `우리 아이는 여러 STEAM 역량에서 뛰어난 강점을 보이며, 특히 ${highScores.map(s => s.category).join(', ')} 영역에서 탁월한 잠재력을 가지고 있습니다. 이러한 강점을 바탕으로 융합적 사고를 발전시켜 나갈 수 있습니다.`;
    } else if (highScores.length > 0) {
        profile.overallSummary = `우리 아이는 ${highScores.map(s => s.category).join(', ')} 영역에서 뚜렷한 강점을 보입니다. 이 강점을 더욱 발전시키면서, 다른 영역들도 균형 있게 성장할 수 있도록 지원하는 것이 중요합니다.`;
    } else if (lowScores.length >= 3) {
        profile.overallSummary = `우리 아이는 ${lowScores.map(s => s.category).join(', ')} 영역에서 성장의 기회가 있습니다. 맞춤형 접근을 통해 이러한 영역들을 강화하면 더욱 균형 잡힌 학습자로 성장할 수 있을 것입니다.`;
    } else {
        profile.overallSummary = "우리 아이는 다양한 학습 역량에서 고르게 발전하고 있으며, 모든 STEAM 영역에서 무한한 성장 가능성을 가지고 있습니다. 꾸준한 관심과 지원으로 아이의 잠재력을 최대한 이끌어낼 수 있습니다.";
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
            <h2 class="text-2xl font-semibold text-gray-500 mb-2">우리 아이의 STEAM 학습 성향 분석 결과</h2>
            <h1 class="text-3xl font-bold text-indigo-600 mb-4">${resultProfile.overallSummary}</h1>
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

function copyResults() {
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

* 우리 아이의 STEAM 학습 성향 분석 요약:
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


function restartAssessment() {
    currentStep = 'intro';
    answers = {};
    currentQuestionIndex = 0;
    studentInfo = { name: '', grade: '' };

    document.getElementById('result-screen').classList.add('hidden');
    document.getElementById('intro-screen').classList.remove('hidden');
}