"""
Database module for progress tracking.

This module handles all SQLite database operations including:
- Initialising database schema
- Managing vocabulary entries
- Tracking progress and mastery levels
- Recording quiz results
"""

import aiosqlite
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class MandarinDatabase:
    """
    Manages the SQLite database for tracking learning progress.
    
    The database uses four main tables:
    - vocabulary: HSK vocabulary with Chinese, pinyin, and English
    - user_progress: Tracks mastery level for each vocabulary item
    - quiz_results: Records quiz attempts and scores
    - learning_sessions: Logs study sessions
    """
    
    def __init__(self, db_path: str = "mandarin_learning.db"):
        """
        Initialise database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> None:
        """Establish connection to the database."""
        self._connection = await aiosqlite.connect(self.db_path)
        # Enable foreign keys for referential integrity
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._connection.commit()
    
    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    async def initialise_schema(self) -> None:
        """
        Create all database tables if they don't exist.
        
        Method is idempotent - safe to call multiple times.
        """
        if not self._connection:
            raise RuntimeError("Database not connected. Call connect() first.")
        
        # Vocab table: stores all HSK words and phrases
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chinese TEXT NOT NULL,
                pinyin TEXT NOT NULL,
                english TEXT NOT NULL,
                hsk_level INTEGER NOT NULL CHECK(hsk_level BETWEEN 1 AND 6),
                word_type TEXT,
                example_sentence TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chinese, hsk_level)
            )
        """)
        
        # User progress table: tracks learning progress for each word
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_id INTEGER NOT NULL,
                mastery_level INTEGER DEFAULT 0 CHECK(mastery_level BETWEEN 0 AND 5),
                times_seen INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                times_incorrect INTEGER DEFAULT 0,
                last_reviewed TIMESTAMP,
                next_review TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vocabulary_id) REFERENCES vocabulary(id) ON DELETE CASCADE,
                UNIQUE(vocabulary_id)
            )
        """)
        
        # Quiz results table: records each quiz attempt
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_type TEXT NOT NULL,
                hsk_level INTEGER CHECK(hsk_level BETWEEN 1 AND 6),
                total_questions INTEGER NOT NULL,
                correct_answers INTEGER NOT NULL,
                score_percentage REAL NOT NULL,
                duration_seconds INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Learning sessions table: tracks study sessions
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS learning_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_type TEXT NOT NULL,
                items_studied INTEGER DEFAULT 0,
                duration_seconds INTEGER,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indices for better query performance
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_vocabulary_hsk 
            ON vocabulary(hsk_level)
        """)
        
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_progress_mastery 
            ON user_progress(mastery_level)
        """)
        
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_progress_next_review 
            ON user_progress(next_review)
        """)
        
        await self._connection.commit()
    
    async def add_vocabulary(
        self,
        chinese: str,
        pinyin: str,
        english: str,
        hsk_level: int,
        word_type: Optional[str] = None,
        example_sentence: Optional[str] = None
    ) -> int:
        """
        Add new vocab item to the database.
        
        Args:
            chinese: Chinese characters
            pinyin: Romanised pronunciation
            english: English translation
            hsk_level: HSK level (1-6)
            word_type: Type of word (noun, verb, adjective, etc.)
            example_sentence: Example usage in Chinese
        
        Returns:
            ID of inserted vocab item
        
        Raises:
            ValueError: If HSK level is not between 1 and 6
        """
        if not 1 <= hsk_level <= 6:
            raise ValueError(f"HSK level must be between 1 and 6, got {hsk_level}")
        
        cursor = await self._connection.execute(
            """
            INSERT INTO vocabulary 
            (chinese, pinyin, english, hsk_level, word_type, example_sentence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chinese, pinyin, english, hsk_level, word_type, example_sentence)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_vocabulary_by_hsk_level(
        self, 
        hsk_level: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve vocab for specific HSK level.
        
        Args:
            hsk_level: HSK level to retrieve (1-6)
            limit: Maximum number of items to return
        
        Returns:
            List of vocab dictionaries
        """
        query = "SELECT * FROM vocabulary WHERE hsk_level = ?"
        params = [hsk_level]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        
        # Convert to list of dictionaries
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def update_progress(
        self,
        vocabulary_id: int,
        correct: bool
    ) -> None:
        """
        Update progress for vocab item after quiz attempt.
        
        This implements a spaced repetition algorithm where:
        - Correct answers increase mastery level
        - Incorrect answers decrease mastery level
        - Next review time is calculated based on mastery level
        
        Args:
            vocabulary_id: vocab item ID
            correct: Whether the user answered correctly
        """
        # First, check if progress entry exists
        cursor = await self._connection.execute(
            "SELECT * FROM user_progress WHERE vocabulary_id = ?",
            (vocabulary_id,)
        )
        existing = await cursor.fetchone()
        
        now = datetime.now().isoformat()
        
        if existing:
            # Update existing progress
            mastery_change = 1 if correct else -1
            new_mastery = max(0, min(5, existing[2] + mastery_change))  # existing[2] is mastery_level
            
            # Calculate next review time based on mastery (simple spaced repetition)
            # Days until next review: 1, 3, 7, 14, 30, 60
            days_map = {0: 1, 1: 3, 2: 7, 3: 14, 4: 30, 5: 60}
            
            await self._connection.execute(
                """
                UPDATE user_progress 
                SET mastery_level = ?,
                    times_seen = times_seen + 1,
                    times_correct = times_correct + ?,
                    times_incorrect = times_incorrect + ?,
                    last_reviewed = ?,
                    next_review = datetime(?, '+' || ? || ' days'),
                    updated_at = ?
                WHERE vocabulary_id = ?
                """,
                (
                    new_mastery,
                    1 if correct else 0,
                    0 if correct else 1,
                    now,
                    now,
                    days_map[new_mastery],
                    now,
                    vocabulary_id
                )
            )
        else:
            # Create new progress entry
            initial_mastery = 1 if correct else 0
            
            await self._connection.execute(
                """
                INSERT INTO user_progress 
                (vocabulary_id, mastery_level, times_seen, times_correct, times_incorrect, 
                 last_reviewed, next_review)
                VALUES (?, ?, 1, ?, ?, ?, datetime(?, '+1 day'))
                """,
                (
                    vocabulary_id,
                    initial_mastery,
                    1 if correct else 0,
                    0 if correct else 1,
                    now,
                    now
                )
            )
        
        await self._connection.commit()
    
    async def get_progress_stats(self) -> Dict[str, Any]:
        """
        Get overall learning progress statistics.
        
        Returns:
            Dictionary with statistics including:
            - total_words_studied: Number of unique words seen
            - mastery_breakdown: Count of words at each mastery level
            - total_reviews: Total number of review sessions
            - accuracy: Overall accuracy percentage
        """
        # Total words studied
        cursor = await self._connection.execute(
            "SELECT COUNT(*) FROM user_progress WHERE times_seen > 0"
        )
        total_studied = (await cursor.fetchone())[0]
        
        # Mastery breakdown
        cursor = await self._connection.execute(
            """
            SELECT mastery_level, COUNT(*) 
            FROM user_progress 
            GROUP BY mastery_level
            ORDER BY mastery_level
            """
        )
        mastery_breakdown = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Total reviews and accuracy
        cursor = await self._connection.execute(
            """
            SELECT 
                SUM(times_seen) as total_reviews,
                SUM(times_correct) as total_correct,
                SUM(times_incorrect) as total_incorrect
            FROM user_progress
            """
        )
        row = await cursor.fetchone()
        total_reviews = row[0] or 0
        total_correct = row[1] or 0
        total_incorrect = row[2] or 0
        
        accuracy = (total_correct / total_reviews * 100) if total_reviews > 0 else 0
        
        return {
            "total_words_studied": total_studied,
            "mastery_breakdown": mastery_breakdown,
            "total_reviews": total_reviews,
            "accuracy": round(accuracy, 2),
            "total_correct": total_correct,
            "total_incorrect": total_incorrect
        }
    
    async def record_quiz_result(
        self,
        quiz_type: str,
        hsk_level: Optional[int],
        total_questions: int,
        correct_answers: int,
        duration_seconds: Optional[int] = None
    ) -> int:
        """
        Record results of quiz session.
        
        Args:
            quiz_type: Type of quiz (e.g., "vocabulary", "mixed")
            hsk_level: HSK level tested (or None for mixed)
            total_questions: Number of questions in the quiz
            correct_answers: Number of correct answers
            duration_seconds: Time taken to complete quiz
        
        Returns:
            ID of inserted quiz result
        """
        score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        cursor = await self._connection.execute(
            """
            INSERT INTO quiz_results 
            (quiz_type, hsk_level, total_questions, correct_answers, score_percentage, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (quiz_type, hsk_level, total_questions, correct_answers, score_percentage, duration_seconds)
        )
        await self._connection.commit()
        return cursor.lastrowid
    
    async def get_quiz_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent quiz results.
        
        Args:
            limit: Maximum number of results to return
        
        Returns:
            List of quiz result dictionaries, ordered by most recent first
        """
        cursor = await self._connection.execute(
            """
            SELECT id, quiz_type, hsk_level, total_questions, correct_answers, 
                   score_percentage, duration_seconds, created_at
            FROM quiz_results 
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_words_for_review(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get vocab items due for review based on spaced repetition.
        
        Args:
            limit: Maximum number of words to return
        
        Returns:
            List of vocab items with progress information
        """
        cursor = await self._connection.execute(
            """
            SELECT v.*, up.mastery_level, up.times_seen, up.last_reviewed
            FROM vocabulary v
            INNER JOIN user_progress up ON v.id = up.vocabulary_id
            WHERE up.next_review <= datetime('now')
            ORDER BY up.next_review ASC
            LIMIT ?
            """,
            (limit,)
        )
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def clear_all_progress(self) -> None:
        """
        Clear all user progress data.
        
        Warning: Deletes all progress tracking but keeps vocab intact.
        """
        await self._connection.execute("DELETE FROM user_progress")
        await self._connection.execute("DELETE FROM quiz_results")
        await self._connection.execute("DELETE FROM learning_sessions")
        await self._connection.commit()