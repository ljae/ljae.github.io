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

    // 카테고리 배지 업데이트
    const badge = document.getElementById('category-badge');
    if (question.category === 'anxiety') {
        badge.className = 'text-xs px-2 py-1 rounded-full bg-rose-100 text-rose-700 font-medium';
        badge.textContent = '불안 척도';
        document.getElementById('question-category').innerHTML = '😰 불안 측정';
        document.getElementById('question-category').className = 'inline-block px-3 py-1.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700';
    } else {
        badge.className = 'text-xs px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-medium';
        badge.textContent = '의지 척도';
        document.getElementById('question-category').innerHTML = '🗣️ 의지 측정';
        document.getElementById('question-category').className = 'inline-block px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700';
    }

    // 핵심문항 배지
    const coreBadge = document.getElementById('core-badge');
    if (question.weight > 1.0) {
        coreBadge.classList.remove('hidden');
    } else {
        coreBadge.classList.add('hidden');
    }

    // 질문 텍스트
    document.getElementById('question-text').textContent = question.text;
    document.getElementById('question-text-en').textContent = question.textEn;

    // 답변 옵션 생성
    const optionsContainer = document.getElementById('answer-options');
    optionsContainer.innerHTML = '';

    likertOptions.forEach(option => {
        const button = document.createElement('button');
        button.className = 'w-full p-5 rounded-2xl border-2 transition-all duration-300 flex items-center gap-4';

        const isSelected = answers[question.id] === option.value;
        if (isSelected) {
            button.className += ' border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-lg transform scale-[1.02]';
        } else {
            button.className += ' border-gray-200 hover:border-indigo-200 hover:bg-gray-50 hover:shadow-md';
        }

        button.onclick = () => selectAnswer(question.id, option.value);

        const emoji = document.createElement('span');
        emoji.className = 'text-3xl';
        emoji.textContent = option.emoji;

        const labelDiv = document.createElement('div');
        labelDiv.className = 'flex-1 text-left';

        const label = document.createElement('span');
        label.className = 'font-semibold text-lg ' + (isSelected ? 'text-indigo-700' : 'text-gray-700');
        label.textContent = option.label;

        labelDiv.appendChild(label);

        if (isSelected) {
            const checkmark = document.createElement('div');
            checkmark.className = 'w-6 h-6 bg-indigo-500 rounded-full flex items-center justify-center';
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

// 점수 계산 (파일 계속...)
