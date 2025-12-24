"""
Testing and quiz module.

Handles:
- Quiz generation from vocab
- Answer checking and scoring
- Progress updates from quiz results
- Quiz session management
"""

import random
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .database import MandarinDatabase
from .vocabulary import VocabularyManager


class Quiz:
    """
    Stores quiz questions, correct answers, tracks user responses.
    """
    
    def __init__(
        self,
        quiz_id: str,
        hsk_level: int,
        questions: List[Dict[str, Any]],
        quiz_type: str = "translation"
    ):
        """
        Initialise quiz.
        
        Args:
            quiz_id: ID
            hsk_level: HSK level being tested
            questions: List of question dictionaries
            quiz_type: Type of quiz (translation, multiple_choice, etc.)
        """
        self.quiz_id = quiz_id
        self.hsk_level = hsk_level
        self.questions = questions
        self.quiz_type = quiz_type
        self.start_time = datetime.now()
        self.user_answers: List[str] = []
        self.is_completed = False
    
    def get_duration_seconds(self) -> int:
        """Get duration of quiz in seconds."""
        end_time = datetime.now()
        return int((end_time - self.start_time).total_seconds())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert quiz to dictionary for serialisation."""
        return {
            "quiz_id": self.quiz_id,
            "hsk_level": self.hsk_level,
            "quiz_type": self.quiz_type,
            "num_questions": len(self.questions),
            "questions": self.questions,
            "start_time": self.start_time.isoformat()
        }


class QuizManager:
    """
    Manages quiz generation, scoring, and progress tracking.
    
    Handles different quiz types and maintains active quiz sessions.
    """
    
    def __init__(self, db: MandarinDatabase, vocab_manager: VocabularyManager):
        """
        Initialise quiz manager.
        
        Args:
            db: Database instance for storing results
            vocab_manager: Vocab manager for selecting words
        """
        self.db = db
        self.vocab_manager = vocab_manager
        self.active_quizzes: Dict[str, Quiz] = {}
    
    async def generate_translation_quiz(
        self,
        hsk_level: int,
        num_questions: int = 5,
        direction: str = "chinese_to_english"
    ) -> Quiz:
        """
        Generate translation quiz (Chinese to English or vice versa).
        
        Args:
            hsk_level: HSK level to quiz on
            num_questions: Number of questions to generate
            direction: "chinese_to_english" or "english_to_chinese"
        
        Returns:
            Quiz object
        """
        # Get vocab for this level
        vocab_list = await self.db.get_vocabulary_by_hsk_level(hsk_level, limit=None)
        
        if len(vocab_list) < num_questions:
            num_questions = len(vocab_list)
        
        # Randomly select questions
        selected = random.sample(vocab_list, num_questions)
        
        questions = []
        for vocab in selected:
            if direction == "chinese_to_english":
                question = {
                    "question": f"What does '{vocab['chinese']}' ({vocab['pinyin']}) mean in English?",
                    "vocab_id": vocab['id'],
                    "chinese": vocab['chinese'],
                    "pinyin": vocab['pinyin'],
                    "correct_answer": vocab['english'].lower().strip(),
                    "question_type": "translation"
                }
            else:  # english_to_chinese
                question = {
                    "question": f"How do you say '{vocab['english']}' in Chinese? (Pinyin: {vocab['pinyin']})",
                    "vocab_id": vocab['id'],
                    "english": vocab['english'],
                    "correct_answer": vocab['chinese'],
                    "pinyin_hint": vocab['pinyin'],
                    "question_type": "translation"
                }
            
            questions.append(question)
        
        # Create quiz
        quiz_id = str(uuid.uuid4())
        quiz = Quiz(quiz_id, hsk_level, questions, quiz_type="translation")
        self.active_quizzes[quiz_id] = quiz
        
        return quiz
    
    async def generate_multiple_choice_quiz(
        self,
        hsk_level: int,
        num_questions: int = 5
    ) -> Quiz:
        """
        Generate multiple choice quiz.
        
        Args:
            hsk_level: HSK level to quiz on
            num_questions: Number of questions to generate
        
        Returns:
            Quiz object
        """
        # Get vocab for this level
        vocab_list = await self.db.get_vocabulary_by_hsk_level(hsk_level, limit=None)
        
        if len(vocab_list) < num_questions:
            num_questions = len(vocab_list)
        
        if len(vocab_list) < 4:
            raise ValueError("Need at least 4 vocabulary items for multiple choice")
        
        # Randomly select questions
        selected = random.sample(vocab_list, num_questions)
        
        questions = []
        for vocab in selected:
            # Generate wrong answers (distractors)
            other_vocab = [v for v in vocab_list if v['id'] != vocab['id']]
            distractors = random.sample(other_vocab, min(3, len(other_vocab)))
            
            # Create choices (correct answer + 3 wrong answers)
            choices = [vocab['english']] + [d['english'] for d in distractors[:3]]
            random.shuffle(choices)
            
            # Find index of correct answer (A, B, C, or D)
            correct_index = choices.index(vocab['english'])
            correct_letter = chr(65 + correct_index)  # 65 is ASCII for 'A'
            
            question = {
                "question": f"What does '{vocab['chinese']}' ({vocab['pinyin']}) mean?",
                "vocab_id": vocab['id'],
                "chinese": vocab['chinese'],
                "pinyin": vocab['pinyin'],
                "choices": {
                    "A": choices[0],
                    "B": choices[1],
                    "C": choices[2],
                    "D": choices[3] if len(choices) > 3 else choices[0]
                },
                "correct_answer": correct_letter,
                "question_type": "multiple_choice"
            }
            
            questions.append(question)
        
        # Create quiz
        quiz_id = str(uuid.uuid4())
        quiz = Quiz(quiz_id, hsk_level, questions, quiz_type="multiple_choice")
        self.active_quizzes[quiz_id] = quiz
        
        return quiz
    
    def check_answer(
        self,
        question: Dict[str, Any],
        user_answer: str
    ) -> Tuple[bool, str]:
        """
        Checks user's answers.
        
        Args:
            question: Question dictionary
            user_answer: User's answer
        
        Returns:
            Tuple of (is_correct, feedback_message)
        """
        user_answer = user_answer.strip()
        
        if question['question_type'] == "multiple_choice":
            # For multiple choice, exact match of letter (case-insensitive)
            correct_answer = question['correct_answer'].upper()
            user_answer_upper = user_answer.upper()
            
            is_correct = user_answer_upper == correct_answer
            if is_correct:
                feedback = "✅ Correct!"
            else:
                correct_choice = question['choices'][correct_answer]
                feedback = f"❌ Incorrect. The correct answer is {correct_answer}: {correct_choice}"
        
        else:  # translation
            # For translation, allow some flexibility
            # Split by commas to handle multiple acceptable answers
            correct_answer = question['correct_answer'].lower()
            user_answer_lower = user_answer.lower()
            acceptable_answers = [ans.strip().lower() for ans in correct_answer.split(',')]
            
            is_correct = any(
                user_answer_lower == acceptable or 
                user_answer_lower in acceptable or
                acceptable in user_answer_lower
                for acceptable in acceptable_answers
            )
            
            if is_correct:
                feedback = "✅ Correct!"
            else:
                feedback = f"❌ Incorrect. The correct answer is: {question['correct_answer']}"
        
        return is_correct, feedback
    
    async def submit_quiz(
        self,
        quiz_id: str,
        answers: List[str]
    ) -> Dict[str, Any]:
        """
        Submit quiz and calculate score.
        
        Args:
            quiz_id: ID of quiz being submitted
            answers: List of user answers
        
        Returns:
            Dictionary with results including score, feedback, and updated progress
        """
        if quiz_id not in self.active_quizzes:
            raise ValueError(f"Quiz {quiz_id} not found or already completed")
        
        quiz = self.active_quizzes[quiz_id]
        
        if len(answers) != len(quiz.questions):
            raise ValueError(
                f"Expected {len(quiz.questions)} answers, got {len(answers)}"
            )
        
        # Check each answer
        results = []
        correct_count = 0
        
        for i, (question, answer) in enumerate(zip(quiz.questions, answers)):
            is_correct, feedback = self.check_answer(question, answer)
            
            if is_correct:
                correct_count += 1
            
            results.append({
                "question_number": i + 1,
                "question": question['question'],
                "user_answer": answer,
                "correct_answer": question['correct_answer'],
                "is_correct": is_correct,
                "feedback": feedback
            })
            
            # Update vocab progress
            await self.db.update_progress(question['vocab_id'], correct=is_correct)
        
        # Calculate score
        total_questions = len(quiz.questions)
        score_percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        # Record result in database
        duration = quiz.get_duration_seconds()
        await self.db.record_quiz_result(
            quiz_type=quiz.quiz_type,
            hsk_level=quiz.hsk_level,
            total_questions=total_questions,
            correct_answers=correct_count,
            duration_seconds=duration
        )
        
        # Mark quiz as completed and remove from active quizzes
        quiz.is_completed = True
        del self.active_quizzes[quiz_id]
        
        return {
            "quiz_id": quiz_id,
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "incorrect_answers": total_questions - correct_count,
            "score_percentage": round(score_percentage, 1),
            "duration_seconds": duration,
            "results": results
        }
    
    def get_active_quiz(self, quiz_id: str) -> Optional[Quiz]:
        """Get active quiz by ID."""
        return self.active_quizzes.get(quiz_id)
    
    def format_quiz_for_display(self, quiz: Quiz) -> str:
        """
        Format quiz for display to user.
        
        Args:
            quiz: Quiz object
        
        Returns:
            Formatted string
        """
        output = f"📝 **Quiz #{quiz.quiz_id[:8]}** (HSK {quiz.hsk_level})\n"
        output += f"Type: {quiz.quiz_type.replace('_', ' ').title()}\n"
        output += f"Questions: {len(quiz.questions)}\n\n"
        
        for i, question in enumerate(quiz.questions, 1):
            output += f"**Question {i}:**\n"
            output += f"{question['question']}\n"
            
            if question['question_type'] == "multiple_choice":
                output += "\nChoices:\n"
                for letter, choice in question['choices'].items():
                    output += f"  {letter}. {choice}\n"
            
            output += "\n"
        
        output += "💡 **To submit your answers, use the submit_quiz_answers tool with your answers as a list.**"
        
        return output
    
    def format_results_for_display(self, results: Dict[str, Any]) -> str:
        """
        Format quiz results for display.
        
        Args:
            results: Results dictionary from submit_quiz
        
        Returns:
            Formatted string
        """
        score = results['score_percentage']
        correct = results['correct_answers']
        total = results['total_questions']
        
        # Determine grade and emoji
        if score >= 90:
            grade = "Excellent! 🌟"
        elif score >= 70:
            grade = "Good job! ✅"
        elif score >= 50:
            grade = "Not bad! 📝"
        else:
            grade = "Keep practicing! 📚"
        
        output = f"""🎯 **Quiz Results**

**Score:** {correct}/{total} ({score}%)
**Grade:** {grade}
**Time:** {results['duration_seconds']} seconds

**Detailed Results:**
"""
        
        for result in results['results']:
            output += f"\n**Q{result['question_number']}:** {result['question']}\n"
            output += f"  Your answer: {result['user_answer']}\n"
            output += f"  {result['feedback']}\n"
        
        output += "\n💡 **Tip:** Your progress has been updated based on these results!"
        
        return output