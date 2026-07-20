import json
import urllib.request
import urllib.error

API_BASE = 'http://127.0.0.1:8000'


def request_json(path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(API_BASE + path, data=data, headers=headers, method='POST' if payload is not None else 'GET')
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'ignore')
        raise RuntimeError(detail or str(exc))


def find_subtopic(topic_name):
    subjects = request_json('/api/subjects')
    search = topic_name.lower()
    for subject in subjects:
        topics = request_json(f'/api/topics/{subject["id"]}')
        for topic in topics:
            if search in topic['name'].lower():
                subtopics = request_json(f'/api/subtopics/{topic["id"]}')
                if subtopics:
                    return subtopics[0]
            for subtopic in request_json(f'/api/subtopics/{topic["id"]}'):
                if search in subtopic['name'].lower():
                    return subtopic
    return None


def main():
    topic = input('Enter topic or subtopic: ').strip()
    confusion = input('Enter confusion score (0-100): ').strip()
    if not topic:
        print('Topic is required.')
        return
    try:
        confusion_value = float(confusion)
    except ValueError:
        print('Confusion score must be a number.')
        return

    subtopic = find_subtopic(topic)
    if not subtopic:
        print('No matching topic or subtopic found.')
        return

    questions = request_json('/api/generate-quiz', {
        'subtopic_id': subtopic['id'],
        'confusion_score': confusion_value,
    })

    print(f'Loaded {len(questions)} questions for {subtopic["name"]}.')
    for idx, question in enumerate(questions, 1):
        print(f"\n{idx}. {question['question']}")
        print(f"A. {question['optionA']}")
        print(f"B. {question['optionB']}")
        print(f"C. {question['optionC']}")
        print(f"D. {question['optionD']}")
        answer = input('Your answer (A-D): ').strip().upper()
        if answer == question['correct_answer']:
            print('Correct!')
        else:
            print(f'Wrong. Correct answer: {question["correct_answer"]}')

    print('Quiz finished.')


if __name__ == '__main__':
    main()
