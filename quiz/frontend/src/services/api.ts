export const API_URL = "http://localhost:8000/api";

export const getSubjects = async () => {
    const res = await fetch(`${API_URL}/subjects`);
    return res.json();
};

export const getTopics = async (subjectId: number) => {
    const res = await fetch(`${API_URL}/topics/${subjectId}`);
    return res.json();
};

export const getSubtopics = async (topicId: number) => {
    const res = await fetch(`${API_URL}/subtopics/${topicId}`);
    return res.json();
};

export const generateQuiz = async (subtopicId: number, confusionScore: number) => {
    const res = await fetch(`${API_URL}/generate-quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            subtopic_id: subtopicId,
            confusion_score: confusionScore
        })
    });
    return res.json();
};

export const submitQuiz = async (data: { subtopic_id: number; confusion_score: number; score: number; time_taken: number }) => {
    const res = await fetch(`${API_URL}/submit-quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    return res.json();
};
