import { useState, useEffect } from 'react';
import { getSubjects, getTopics, getSubtopics, generateQuiz, submitQuiz } from './services/api';

type Step = 'SUBJECT' | 'TOPIC' | 'SUBTOPIC' | 'CONFUSION' | 'QUIZ' | 'RESULT';

export default function App() {
  const [step, setStep] = useState<Step>('SUBJECT');
  const [subjects, setSubjects] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);
  const [subtopics, setSubtopics] = useState<any[]>([]);
  
  const [selectedSubject, setSelectedSubject] = useState<any>(null);
  const [selectedTopic, setSelectedTopic] = useState<any>(null);
  const [selectedSubtopic, setSelectedSubtopic] = useState<any>(null);
  
  const [confusionScore, setConfusionScore] = useState<number>(50);
  
  const [questions, setQuestions] = useState<any[]>([]);
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  
  const [score, setScore] = useState(0);
  const [timeTaken, setTimeTaken] = useState(0);
  const [timer, setTimer] = useState<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getSubjects().then(setSubjects);
  }, []);

  const handleSubjectSelect = (sub: any) => {
    setSelectedSubject(sub);
    getTopics(sub.id).then(setTopics);
    setStep('TOPIC');
  };

  const handleTopicSelect = (top: any) => {
    setSelectedTopic(top);
    getSubtopics(top.id).then(setSubtopics);
    setStep('SUBTOPIC');
  };

  const handleSubtopicSelect = (subtop: any) => {
    setSelectedSubtopic(subtop);
    setStep('CONFUSION');
  };

  const handleStartQuiz = async () => {
    const qs = await generateQuiz(selectedSubtopic.id, confusionScore);
    if (qs && qs.length > 0) {
      setQuestions(qs);
      setStep('QUIZ');
      setAnswers({});
      setCurrentQuestionIdx(0);
      setTimeTaken(0);
      const t = setInterval(() => {
        setTimeTaken(prev => prev + 1);
      }, 1000);
      setTimer(t);
    } else {
      alert("No questions found for this subtopic and difficulty distribution.");
    }
  };

  const handleAnswerSelect = (opt: string) => {
    setAnswers(prev => ({ ...prev, [currentQuestionIdx]: opt }));
  };

  const handleNextQuestion = () => {
    if (currentQuestionIdx < questions.length - 1) {
      setCurrentQuestionIdx(prev => prev + 1);
    } else {
      finishQuiz();
    }
  };

  const finishQuiz = async () => {
    if (timer) clearInterval(timer);
    
    let finalScore = 0;
    questions.forEach((q, idx) => {
      if (answers[idx] === q.correct_answer) {
        finalScore += 1;
      }
    });
    setScore(finalScore);
    
    await submitQuiz({
      subtopic_id: selectedSubtopic.id,
      confusion_score: confusionScore,
      score: finalScore,
      time_taken: timeTaken
    });
    
    setStep('RESULT');
  };

  const reset = () => {
    setStep('SUBJECT');
    setSelectedSubject(null);
    setSelectedTopic(null);
    setSelectedSubtopic(null);
  };

  return (
    <div className="w-screen h-screen overflow-hidden bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600/20 to-purple-600/20 backdrop-blur-md border-b border-purple-500/20 px-6 py-4 flex justify-between items-center">
        <h1 className="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400">
          🎓 Quiz Master
        </h1>
        {step !== 'SUBJECT' && step !== 'RESULT' && (
          <div className="text-sm text-gray-300 font-medium">
            <span className="text-indigo-400">{selectedSubject?.name}</span>
            {selectedTopic && <span className="mx-2 text-gray-500">→</span>}
            {selectedTopic && <span className="text-purple-400">{selectedTopic?.name}</span>}
            {selectedSubtopic && <span className="mx-2 text-gray-500">→</span>}
            {selectedSubtopic && <span className="text-pink-400">{selectedSubtopic?.name}</span>}
          </div>
        )}
        {step === 'RESULT' && (
          <div className="text-sm font-semibold text-green-400">Quiz Completed ✓</div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto px-6 py-8">
        <div className="max-w-5xl mx-auto h-full flex flex-col justify-center">
          
          {step === 'SUBJECT' && (
            <div className="animate-fade-in space-y-8">
              <div className="text-center space-y-3">
                <h2 className="text-4xl font-bold">Select Your Subject</h2>
                <p className="text-gray-400 text-lg">Choose a subject to begin your quiz journey</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
                {subjects.map(sub => (
                  <button key={sub.id} onClick={() => handleSubjectSelect(sub)}
                    className="group relative overflow-hidden bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 hover:border-indigo-500 p-8 rounded-2xl transition-all duration-300 transform hover:scale-105 hover:shadow-2xl hover:shadow-indigo-500/20">
                    <div className="absolute inset-0 bg-gradient-to-r from-indigo-600/0 to-purple-600/0 group-hover:from-indigo-600/10 group-hover:to-purple-600/10 transition-all duration-300" />
                    <div className="relative z-10 flex flex-col items-center justify-center h-32">
                      <div className="text-4xl mb-3 group-group-hover:scale-110 transition-transform">📚</div>
                      <span className="text-2xl font-bold text-center">{sub.name}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 'TOPIC' && (
            <div className="animate-fade-in space-y-8">
              <div className="text-center space-y-3">
                <h2 className="text-4xl font-bold">Select Topic in {selectedSubject?.name}</h2>
                <p className="text-gray-400 text-lg">Choose a topic to explore</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-12">
                {topics.map(top => (
                  <button key={top.id} onClick={() => handleTopicSelect(top)}
                    className="group relative overflow-hidden bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 hover:border-purple-500 p-8 rounded-2xl transition-all duration-300 transform hover:scale-105 hover:shadow-2xl hover:shadow-purple-500/20">
                    <div className="absolute inset-0 bg-gradient-to-r from-purple-600/0 to-pink-600/0 group-hover:from-purple-600/10 group-hover:to-pink-600/10 transition-all duration-300" />
                    <div className="relative z-10 text-center">
                      <span className="text-xl font-bold">{top.name}</span>
                    </div>
                  </button>
                ))}
              </div>
              
              <button onClick={() => setStep('SUBJECT')} className="mt-8 mx-auto block text-indigo-400 hover:text-indigo-300 font-semibold transition-colors">
                ← Back to Subjects
              </button>
            </div>
          )}

          {step === 'SUBTOPIC' && (
            <div className="animate-fade-in space-y-8">
              <div className="text-center space-y-3">
                <h2 className="text-4xl font-bold">Select Subtopic</h2>
                <p className="text-gray-400 text-lg">{selectedTopic?.name}</p>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-12">
                {subtopics.map(subtop => (
                  <button key={subtop.id} onClick={() => handleSubtopicSelect(subtop)}
                    className="group relative overflow-hidden bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 hover:border-pink-500 p-8 rounded-2xl transition-all duration-300 transform hover:scale-105 hover:shadow-2xl hover:shadow-pink-500/20">
                    <div className="absolute inset-0 bg-gradient-to-r from-pink-600/0 to-rose-600/0 group-hover:from-pink-600/10 group-hover:to-rose-600/10 transition-all duration-300" />
                    <div className="relative z-10 text-center">
                      <span className="text-xl font-bold">{subtop.name}</span>
                    </div>
                  </button>
                ))}
              </div>
              
              <button onClick={() => setStep('TOPIC')} className="mt-8 mx-auto block text-purple-400 hover:text-purple-300 font-semibold transition-colors">
                ← Back to Topics
              </button>
            </div>
          )}

          {step === 'CONFUSION' && (
            <div className="animate-fade-in flex flex-col items-center justify-center space-y-8">
              <div className="text-center space-y-4 max-w-2xl">
                <h2 className="text-4xl font-bold">How confused are you?</h2>
                <p className="text-gray-400 text-lg">
                  Rate your confusion level (0-100). Higher scores give easier questions to help you learn better.
                </p>
              </div>
              
              <div className="w-full max-w-md bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 p-10 rounded-3xl shadow-2xl">
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={confusionScore} 
                  onChange={(e) => setConfusionScore(Number(e.target.value))}
                  className="w-full h-3 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-indigo-500 slider" 
                />
                <div className="text-center mt-8">
                  <div className="text-6xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-purple-400 mb-2">
                    {confusionScore}
                  </div>
                  <div className="text-gray-400 text-sm">
                    {confusionScore < 20 ? '🔥 Mastered' : confusionScore < 40 ? '💪 Confident' : confusionScore < 60 ? '🤔 Uncertain' : confusionScore < 80 ? '😅 Confused' : '🆘 Very Confused'}
                  </div>
                </div>
              </div>

              <button 
                onClick={handleStartQuiz}
                className="mt-8 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 px-12 py-4 rounded-full font-bold text-lg transition-all transform hover:scale-105 shadow-2xl shadow-indigo-500/50 active:scale-95">
                Start Quiz 🚀
              </button>
              
              <button onClick={() => setStep('SUBTOPIC')} className="mt-4 text-pink-400 hover:text-pink-300 font-semibold transition-colors">
                ← Back to Subtopics
              </button>
            </div>
          )}

          {step === 'QUIZ' && questions.length > 0 && (
            <div className="animate-fade-in space-y-6 h-full flex flex-col">
              {/* Progress Bar */}
              <div className="flex gap-4 items-center">
                <div className="flex-1 bg-gray-800 rounded-full h-2 overflow-hidden border border-gray-700">
                  <div 
                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-300"
                    style={{ width: `${((currentQuestionIdx + 1) / questions.length) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-gray-300 whitespace-nowrap">
                  {currentQuestionIdx + 1} / {questions.length}
                </span>
              </div>

              {/* Timer and Difficulty */}
              <div className="flex justify-between items-center">
                <span className="bg-gradient-to-r from-blue-500/20 to-cyan-500/20 border border-blue-500/30 text-blue-300 px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2">
                  📊 {questions[currentQuestionIdx].difficulty.toUpperCase()}
                </span>
                <span className="bg-gradient-to-r from-rose-500/20 to-red-500/20 border border-rose-500/30 text-rose-300 px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2">
                  ⏱️ {Math.floor(timeTaken / 60)}:{(timeTaken % 60).toString().padStart(2, '0')}
                </span>
              </div>

              {/* Question */}
              <div className="bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700 p-8 rounded-2xl my-6">
                <h3 className="text-2xl font-semibold leading-relaxed">{questions[currentQuestionIdx].question}</h3>
              </div>

              {/* Options */}
              <div className="grid grid-cols-1 gap-4 flex-1">
                {['A', 'B', 'C', 'D'].map(optKey => {
                  const optValue = questions[currentQuestionIdx][`option${optKey}`];
                  const isSelected = answers[currentQuestionIdx] === optKey;
                  return (
                    <button 
                      key={optKey} 
                      onClick={() => handleAnswerSelect(optKey)}
                      className={`p-5 rounded-xl text-left border transition-all duration-200 flex items-start gap-4 group ${
                        isSelected 
                        ? 'bg-gradient-to-r from-indigo-600/40 to-purple-600/40 border-indigo-400 text-white shadow-lg shadow-indigo-500/30 scale-102' 
                        : 'bg-gray-800/50 border-gray-600 text-gray-200 hover:bg-gray-700/50 hover:border-gray-500'
                      }`}>
                      <span className={`font-bold text-lg flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg ${
                        isSelected ? 'bg-indigo-500 text-white' : 'bg-gray-700 text-gray-400 group-hover:bg-gray-600'
                      }`}>
                        {optKey}
                      </span>
                      <span className="flex-1">{optValue}</span>
                    </button>
                  )
                })}
              </div>

              {/* Next Button */}
              <div className="flex justify-end mt-8">
                <button 
                  onClick={handleNextQuestion}
                  disabled={!answers[currentQuestionIdx]}
                  className="bg-gradient-to-r from-indigo-600 to-purple-600 disabled:from-gray-600 disabled:to-gray-600 disabled:cursor-not-allowed hover:from-indigo-500 hover:to-purple-500 px-10 py-4 rounded-full font-bold text-lg transition-all transform hover:scale-105 active:scale-95 disabled:hover:scale-100 shadow-lg">
                  {currentQuestionIdx === questions.length - 1 ? '✅ Submit Quiz' : 'Next →'}
                </button>
              </div>
            </div>
          )}

          {step === 'RESULT' && (
            <div className="animate-fade-in flex flex-col items-center justify-center space-y-8">
              <div className="text-center space-y-2">
                <h2 className="text-5xl font-extrabold">🎉 Quiz Completed!</h2>
                <p className="text-gray-400 text-xl">You finished {selectedSubtopic?.name}</p>
              </div>
              
              <div className="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-3xl p-12 w-full max-w-md shadow-2xl">
                <div className="space-y-6">
                  <div className="text-center">
                    <div className="text-sm uppercase tracking-widest text-gray-400 font-semibold mb-3">Final Score</div>
                    <div className="text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">
                      {score}/{questions.length}
                    </div>
                    <div className="text-lg mt-3 text-gray-300">
                      {Math.round((score / questions.length) * 100)}% Correct
                    </div>
                  </div>
                  
                  <div className="border-t border-gray-700 pt-6 space-y-3">
                    <div className="flex justify-between text-gray-300">
                      <span>Time Taken</span>
                      <span className="font-bold">{Math.floor(timeTaken / 60)}m {(timeTaken % 60)}s</span>
                    </div>
                    <div className="flex justify-between text-gray-300">
                      <span>Difficulty Level</span>
                      <span className="font-bold text-indigo-400">{confusionScore}</span>
                    </div>
                  </div>
                </div>
              </div>

              <button 
                onClick={reset}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 px-12 py-4 rounded-full font-bold text-lg transition-all transform hover:scale-105 active:scale-95 shadow-lg">
                Take Another Quiz 🔄
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
