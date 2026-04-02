import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import re
import logging


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

def get_llm():
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        return model
    except Exception as e:
        logger.error(f"Error initializing Gemini model: {str(e)}")
        raise Exception(f"Failed to initialize AI model: {str(e)}")
    

def generate_tutoring_response(subject, level, question, learning_style, background, language):
    """
    Generate a personalized tutoring response based on user prefernces.
    
    Args:
        subject (str): The academic subject
        level (str): Learning level (Beginner, Intermediate, Advanced)
        question (str): User's specific question
        learning_style (str): Preferred learning style (Visual, Text-based, Hands-on)
        background (str): User's background knowledge
        language (str): Preferred language for response
        
        Returns:
            str: Formatted tutoring response
        """
    try:

        llm = get_llm()


        prompt = _create_tutoring_prompt(subject, level, question, learning_style, background, language)


        logger.info(f"Generating tutoring response for subject: {subject}, level: {level}")
        response = llm.generate_content(prompt)



        return _format_tutoring_response(response.text, learning_style)
    
    except Exception as e:
        logger.error(f"Error generating tutoring response: {str(e)}")
        raise Exception(f"Failed to generate tutoring response: {str(e)}")
    


def _create_tutoring_prompt(subject, level, question, learning_style, background, language):
    """Helper function to create a well-structured prompt for the AI model."""


    prompt = f"""
    You are an expert tutor in {subject} at the {level} level.

    STUDENT PROFILE:
    - Background knowlwdge: {background}
    - Learning style preference: {learning_style}
    - Language preference: {language}

    QUESTION:
    {question}

    INSTRUCTIONS:
    1. Provide a clear, educational explanation that directly addresses the question
    2. Tailor your explanation to a {background} student at {level} level
    3. Use {language} as the primary language
    4. Format your response with appropriate markdown for readability

    LEARNING STYLE ADAPTATIONS:
    - For visual learners: Include descriptions of visual concepts, diagrams, or mentak models
    - For Text_based learners: Provide clear, structured explanations with defined concepts
    - For Hands-on learners: Include practical examples, exercises, or applications

    Your explanation should be educational, accurate ,and engaging.
    """

    return prompt



def _format_tutoring_response(content, learning_style):
    """Helper function to format the tutoring response based on learning style."""
    
    if learning_style == "Visual":
        return content + "\n\n*Note: Visualize these concepts as you read for better retention.*"
    elif learning_style == "Hands_on":
        return content + "\n\n*Tip: Try working through the examples yourself to reinforce your learning.*"
    else:
        return content



def _create_quiz_prompt(subject, level, num_questions, topic=None):
    """Helper function to create a well-structured quiz generation prompt"""
    
    topic_instruction = f"ALL QUESTIONS MUST BE BASED ON THE FOLLOWING TOPIC: '{topic}'." if topic else f"Cover diverse aspects of {subject}."

    return f"""
    Create a {level}-level quiz on {subject} with exactly {num_questions} multiple-choice questions.

    {topic_instruction}

    INSTRUCTIONS:
    1. Each question should be appropriate for {level} level students
    2 . Each question must have exactly 4 answer options (A, B, C, D)
    3. Clearly indicate the correct answer 
    4. Cover diverse aspects of {subject}

    FORMAT YOUR RESPONSE AS JSON:
    ```json
    [
        {{
            "question": "Question text",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A"
            "explanation": "Brief explanation of why this answer is correct"
        }},
        ...
    ]
    ```

    IMPORTANT: Make sure to return valid JSON that can be parsed.Do not include any text outside the JSON array.
    Include a brief explanation of each correct answer.
    """
def _create_fallback_quiz(subject, num_questions):
    """Helper function to create a fallback quiz if parsing fails"""


    logger.warning(f"Using fallback quiz for {subject}")

    return [
        {
            "question": f"Sample {subject} question #{i+1}",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "explanation": "This is a fallback explanation"
        }
        for i in range(num_questions)
    ]



def _validate_quiz_data(quiz_data):
    """Helper function to validate quiz data structure"""

    if not isinstance(quiz_data, list):
        raise ValueError("Quiz data must be a list of questions")
    
    for question in quiz_data:
        if not isinstance(question, dict):
            raise ValueError("Each quiz item must be a dictionary")

        if not all(key in question for key in ["question", "options", "correct_answer"]):
            raise ValueError("Each quiz item must have question, options, and correct_answer")
        
        if not isinstance(question["options"], list) or len(question["options"]) != 4:
            raise ValueError("Each question must have exactly 4 options")
        


def _parse_quiz_response(response_content, subject, num_questions):
    """Helper function to parse and validate the quiz response"""

    try:
        # Try to find JSON content using regex
        json_match = re.search(r'```json\s*(\[[\s\S]*?\])\s*```', response_content)

        if json_match:
            #Extract JSON from code block
            quiz_json = json_match.group(1)
        else:
            # Try to find raw JSON array
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response_content, re.DOTALL)
            if json_match:
                quiz_json = json_match.group(0)
            else:
                # Assume the entire response is JSON
                quiz_json = response_content

        # Parse the JSON
        quiz_data = json.loads(quiz_json)

        # Validate the data structure
        _validate_quiz_data(quiz_data)

        # Ensure we have the requested number of questions
        if len(quiz_data) > num_questions:
            quiz_data = quiz_data[:num_questions]

        # Add explanation field if missing
        for question in quiz_data:
            if "explanation" not in question:
                question["explanation"] = f"The correct answer is {question['correct_answer']}."

        return quiz_data

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error parsing quiz response: {str(e)}")
        
        # Create a fallback quiz if parsing fails
        return _create_fallback_quiz(subject, num_questions)
    



def generate_quiz(subject, level, num_questions=5, reveal_answer=True, topic=None):
    """
    Generate a quiz with multiple-choice questions based on subject and level.

    Args:
        subject (str): The academic subject
        level (str): Learning level (Beginner, Intermediate, Advanced)
        num_questions (int): Number of questions to generate
        reveal_answer (bool): Whether to format the response with hidden answers that can be revealed

    Returns:
        dict: Contains quiz data (list of questions) and formatted HTML if reveal_answer is True
    """
    try:
        # Get LLM instance
        llm = get_llm()

        # Create a structured prompt for quiz generation
        prompt = _create_quiz_prompt(subject, level, num_questions, topic)

        # Generate response
        logger.info(f"Generating quiz for subject: {subject}, level: {level}, questions: {num_questions}")
        
        response = llm.generate_content(prompt)


        # Parse and validate the response
        quiz_data = _parse_quiz_response(response.text, subject, num_questions)

        # Format the quiz with hidden answers if requested
        if reveal_answer:
            formatted_quiz = _format_quiz_with_reveal(quiz_data)
            return {
                "quiz_data": quiz_data,
                "formatted_quiz": formatted_quiz
            }
        else:
            return {
                "quiz_data": quiz_data
            }
        
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        raise Exception(f"Failed to generate quiz: {str(e)}")
    



def _format_quiz_with_reveal(quiz_data):
    """
    Format quiz data into HTML with hidden answers that can be revealed on click.

    Args:
        quiz_data (list): List of question dictionaries

    Returns:
        str: HTML string with quiz questions and hidden answers
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                color: white;
                background-color: #121212;
            }
            .quiz-container {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .question {
                margin-bottom: 30px;
                padding: 20px;
                border: 1px solid #444;
                border-radius: 10px;
                background-color: #1e1e2f;
            }
            .question h3 {
                margin-top: 0;
                color: #90caf9;
            }
            .options {
                margin-left: 10px;
            }
            .option {
                margin: 10px 0;
                padding: 12px;
                border: 1px solid #555;
                border-radius: 5px;
                cursor: pointer;
                background-color: #2d2d44;
                transition: background-color 0.2s;
            }
            option:hover {
                background-color: #3a3a5a;
            }
            .reveal-btn {
                background-color: #2196f3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
                margin-top: 15px;
                transition: background-color 0.2s;
            }
            .reveal-btn:hover {
                background-color: #0d8bf2;
            }
            .answer-section {
                margin-top: 20px;
                border: 2px solid #ffeb3b;
                border-radius: 8px;
                padding: 0;
                overflow: hidden;
                display: none;
            }
            .answer-header {
                background-color: #ffeb3b;
                color: #000;
                padding: 10px;
                font-weight: bold;
                font-size: 16px;
                text-align: center;
            }
            .answer-content {
                padding: 15px;
                background-color: #1a237e;
            }
            .correct-answer {
                font-size: 18px;
                font-weight: bold;
                color: white;
                margin-bottom: 15px;
            }
            .explanation {
                color: #e1f5fe;
                font-size: 16px;
                line-height: 1.5;
            }
            .selected-correct {
                background-color: #1b5e20 !important;
                border-color: #4caf50 !important;
            }
            .selected-incorrect {
                background-color: #b71c1c !important;
                border-color: #f44336 !important;
            }
        </style>
    </head>
    <body>
        <div class="quiz-container">
            <h2 style="color: #2196f3; text-align:center;margin-bottom: 30px;">Interactive Quiz</h2>
    """

    for i, question in enumerate(quiz_data,1):
        option_letters = ["A", "B", "C", "D"]
        correct_index = question["options"].index(question["correct_answer"]) if question["correct_answer"] in question["options"] else 0

        html += f"""
            <div class="question" id="question-{i}">
                <h3>Question {i}</h3>
                <p>{question["question"]}</p>
                <div class="options">
        """
        
        for j, option in enumerate(question["options"]):
            is_correct = j == correct_index
            html += f"""
                    <div class="option" id="option-{i}-{j}"onclick="selectOption({i},{j},{'true' if is_correct else 'false'})">
                        <strong>{option_letters[j]}.</strong>{option}
                    </div>
            """

        html += f"""
                </div>
                <button class="reveal-btn" onclick="revealAnswer({i})">SHOW ANSWER</button>
                <div class="answer-section" id="answer-{i}">
                    <div class="answer-header">CORRECT ANSWER</div>
                    <div class="answer-content">
                        <div class="correct-answer">{option_letters[correct_index]}.{question["correct_answer"]}</div>
                        <div class="explanation">{question.get("explanation","")}</div>
                    </div>
                </div>
            </div>
        """

    html += """
        </div>
        <script>
            function selectOption(questionNum, optionNum, isCorrect) {
                const questionId = `question-${questionNum}`;
                const options = document.querySelectorAll(`#${questionId} .option`);
                                                          
                // Reset all options
                options.forEach(option => {
                    option.className = 'option';
                });

                // Highlight selected option
                const selectedOption = document.getElementById(`option-${questionNum}-${optionNum}`);
                if (isCorrect) {
                    selectedOption.className = 'option selected-correct';
                } else {
                    selectedOption.className = 'option selected-incorrect';
                // Show answer if incorrect 
                revealAnswer(questionNum);
                }
            }

            function revealAnswer(questionNum) {
                const answerDiv = document.getElementById(`answer-${questionNum}`);
                answerDiv.style.display = 'block';

                // Scroll to answer
                setTimeout(() => {
                    answerDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }, 100);

                // Add animation for attention
                answerDiv.animate([
                { transform: 'scale(1)', boxShadow: '0 0 0 rgba(255, 235, 59, 0)' },
                { transform: 'scale(1.03)', boxShadow: '0 0 20px rgba(255, 235, 59, 0.7)' },
                { transform: 'scale(1)', boxShadow: '0 0 10px rgba(255, 235, 59, 0.3)' }
                ], {   
                    duration: 1000,
                    iterations: 1
                });
            }
        </script>
    </body>
    </html>
    """                                      

    return html


def export_quiz_to_html(quiz_data, file_path="quiz.html"):
    """
    Export the formatted quiz to an HTML file
    
    Args:
        quiz_data (list): List of question dictionaries
        file_path(str): Path to save the HTML file
    """
    try:
        html_content = _format_quiz_with_reveal(quiz_data)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Quiz exported successfully to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting quiz to HTML: {str(e)}")
        return False    