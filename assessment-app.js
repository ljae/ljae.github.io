// v4.0 Global State
let currentStep = 'intro'; // 'intro', 'survey', 'result'
let answers = {};
let currentQuestionIndex = 0;
let studentInfo = { name: '', grade: '' };
let resultType = 'C'; // Default to Type C

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
    resultType = getRoadmapType(scores);
    renderResults(resultType);
}

// --- Calculation and Rendering Logic ---

function calculateScores() {
    const scores = {
        expression: 0,
        confidence: 0,
        inquiry: 0,
        thinking: 0
    };
    const counts = { ...scores };

    questions.forEach(q => {
        const answer = answers[q.id] || 3;
        if (scores.hasOwnProperty(q.category)) {
            scores[q.category] += answer * (q.weight || 1);
            counts[q.category] += (q.weight || 1);
        }
    });

    for (const key in scores) {
        if (counts[key] > 0) {
            scores[key] /= counts[key];
        }
    }
    return scores;
}

function getRoadmapType(scores) {
    const { expression, confidence, inquiry, thinking } = scores;

    // Type A: High Expression & High Confidence
    if (expression >= 4.0 && confidence >= 3.8) {
        return 'A';
    }
    // Type B: High Inquiry & Analytical Thinking
    if (inquiry >= 4.0 && thinking >= 3.5) {
        return 'B';
    }
    // Type C: Balanced (default)
    return 'C';
}

function renderResults(type) {
    const resultData = roadmapTypes[type];
    const resultContent = document.getElementById('result-content');

    resultContent.innerHTML = `
        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn text-center">
            <h2 class="text-2xl font-semibold text-gray-500 mb-2">우리 아이의 학습 성향은</h2>
            <p class="text-5xl font-extrabold text-indigo-600 mb-1">${resultData.type}</p>
            <h1 class="text-3xl font-bold text-gray-800 mb-4">${resultData.title}</h1>
            <p class="text-lg font-semibold text-gray-600 mb-8">${resultData.subtitle}</p>
            
            <div class="bg-gray-50 text-left p-6 rounded-xl border border-gray-200">
                <p class="text-gray-700 leading-relaxed">${resultData.description}</p>
            </div>
        </div>

        <div class="bg-white rounded-3xl shadow-2xl p-8 animate-fadeIn">
            <h3 class="text-2xl font-bold text-gray-800 mb-6 text-center">💡 맞춤 성장 전략</h3>
            <ul class="space-y-4">
                ${resultData.recommendations.map(rec => `
                    <li class="flex items-start gap-3 p-4 bg-indigo-50 rounded-xl">
                        <span class="text-2xl mt-1">✨</span>
                        <span class="text-gray-800">${rec}</span>
                    </li>
                `).join('')}
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
    const gradeInput = document.getElementById('student-grade-result');
    const copyButton = document.getElementById('copy-button');

    if (!nameInput.value.trim() || !gradeInput.value) {
        alert('아이 이름과 학년을 모두 입력해주세요.');
        nameInput.focus();
        return;
    }
    
    studentInfo.name = nameInput.value.trim();
    studentInfo.grade = gradeInput.value;

    const resultData = roadmapTypes[resultType];

    const resultText = `
[Open Edu 학습 성향 진단 결과]

- 이름: ${studentInfo.name}
- 학년: ${studentInfo.grade}
- 진단 결과: ${resultData.type} (${resultData.title})

"${resultData.subtitle}"

자세한 상담을 받고 싶습니다.
    `.trim();

    navigator.clipboard.writeText(resultText).then(() => {
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