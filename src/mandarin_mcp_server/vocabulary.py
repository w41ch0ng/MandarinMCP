"""
Vocab management module.

This module handles:
- Loading and managing HSK vocabulary
- Searching and filtering vocabulary
- Selecting vocabulary for learning sessions
- Managing vocabulary categories
"""

import random
from typing import List, Dict, Any, Optional
from .database import MandarinDatabase


class VocabularyManager:
    """
    Manages vocab operations.
    
    Provides methods for selecting vocab based on various criteria
    e.g. HSK level, mastery level, learning history.
    """
    
    def __init__(self, db: MandarinDatabase):
        """
        Initialise vocab manager.
        
        Args:
            db: Database instance for accessing vocab
        """
        self.db = db
    
    async def get_new_vocabulary(
        self,
        hsk_level: int,
        count: int = 5,
        exclude_learned: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get new vocab for learning that user hasn't seen yet.
        
        Args:
            hsk_level: HSK level (1-6)
            count: Number of words to retrieve
            exclude_learned: If True, exclude words user has already studied
        
        Returns:
            List of vocab items
        """
        # Get all vocab for the level
        all_vocab = await self.db.get_vocabulary_by_hsk_level(hsk_level, limit=None)
        
        if exclude_learned:
            # Get list of vocab IDs the user has seen
            cursor = await self.db._connection.execute(
                "SELECT vocabulary_id FROM user_progress WHERE times_seen > 0"
            )
            learned_ids = {row[0] for row in await cursor.fetchall()}
            
            # Filter out learned vocab
            new_vocab = [v for v in all_vocab if v['id'] not in learned_ids]
        else:
            new_vocab = all_vocab
        
        # Shuffle and return requested count
        random.shuffle(new_vocab)
        return new_vocab[:count]
    
    async def get_vocabulary_for_review(
        self,
        hsk_level: Optional[int] = None,
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get vocab items due for review using spaced repetition.
        
        Args:
            hsk_level: Optional HSK level filter (None for all levels)
            count: Maximum number of words to return
        
        Returns:
            List of vocab items due for review
        """
        if hsk_level:
            cursor = await self.db._connection.execute(
                """
                SELECT v.*, up.mastery_level, up.times_seen, up.last_reviewed
                FROM vocabulary v
                INNER JOIN user_progress up ON v.id = up.vocabulary_id
                WHERE v.hsk_level = ? AND up.next_review <= datetime('now')
                ORDER BY up.next_review ASC
                LIMIT ?
                """,
                (hsk_level, count)
            )
        else:
            cursor = await self.db._connection.execute(
                """
                SELECT v.*, up.mastery_level, up.times_seen, up.last_reviewed
                FROM vocabulary v
                INNER JOIN user_progress up ON v.id = up.vocabulary_id
                WHERE up.next_review <= datetime('now')
                ORDER BY up.next_review ASC
                LIMIT ?
                """,
                (count,)
            )
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_vocabulary_by_mastery(
        self,
        mastery_level: int,
        hsk_level: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get vocab filtered by mastery level.
        
        Args:
            mastery_level: Mastery level (0-5)
            hsk_level: Optional HSK level filter
            limit: Maximum number of words to return
        
        Returns:
            List of vocab items at specified mastery level
        """
        if hsk_level:
            cursor = await self.db._connection.execute(
                """
                SELECT v.*, up.mastery_level, up.times_seen, up.times_correct, up.times_incorrect
                FROM vocabulary v
                INNER JOIN user_progress up ON v.id = up.vocabulary_id
                WHERE up.mastery_level = ? AND v.hsk_level = ?
                LIMIT ?
                """,
                (mastery_level, hsk_level, limit)
            )
        else:
            cursor = await self.db._connection.execute(
                """
                SELECT v.*, up.mastery_level, up.times_seen, up.times_correct, up.times_incorrect
                FROM vocabulary v
                INNER JOIN user_progress up ON v.id = up.vocabulary_id
                WHERE up.mastery_level = ?
                LIMIT ?
                """,
                (mastery_level, limit)
            )
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def search_vocabulary(
        self,
        search_term: str,
        hsk_level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search vocab by Chinese characters, pinyin, or English.
        
        Args:
            search_term: Search string (case-insensitive)
            hsk_level: Optional HSK level filter
        
        Returns:
            List of matching vocab items
        """
        search_pattern = f"%{search_term}%"
        
        if hsk_level:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                WHERE (chinese LIKE ? OR pinyin LIKE ? OR english LIKE ?)
                AND hsk_level = ?
                ORDER BY hsk_level, chinese
                """,
                (search_pattern, search_pattern, search_pattern, hsk_level)
            )
        else:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                WHERE chinese LIKE ? OR pinyin LIKE ? OR english LIKE ?
                ORDER BY hsk_level, chinese
                """,
                (search_pattern, search_pattern, search_pattern)
            )
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_vocabulary_by_word_type(
        self,
        word_type: str,
        hsk_level: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get vocab filtered by word type (noun, verb, adjective, etc.).
        
        Args:
            word_type: Type of word (e.g., "noun", "verb", "adjective")
            hsk_level: Optional HSK level filter
            limit: Maximum number of words to return
        
        Returns:
            List of vocab items of specified type
        """
        if hsk_level:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                WHERE word_type = ? AND hsk_level = ?
                ORDER BY chinese
                LIMIT ?
                """,
                (word_type, hsk_level, limit)
            )
        else:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                WHERE word_type = ?
                ORDER BY hsk_level, chinese
                LIMIT ?
                """,
                (word_type, limit)
            )
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_vocabulary_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about vocab database.
        
        Returns:
            Dictionary with statistics including:
            - Total vocab count
            - Count per HSK level
            - Count per word type
        """
        # Total vocab count
        cursor = await self.db._connection.execute(
            "SELECT COUNT(*) FROM vocabulary"
        )
        total_count = (await cursor.fetchone())[0]
        
        # Count per HSK level
        cursor = await self.db._connection.execute(
            """
            SELECT hsk_level, COUNT(*) as count
            FROM vocabulary
            GROUP BY hsk_level
            ORDER BY hsk_level
            """
        )
        hsk_counts = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Count per word type
        cursor = await self.db._connection.execute(
            """
            SELECT word_type, COUNT(*) as count
            FROM vocabulary
            WHERE word_type IS NOT NULL
            GROUP BY word_type
            ORDER BY count DESC
            """
        )
        type_counts = {row[0]: row[1] for row in await cursor.fetchall()}
        
        # Count learned vs new
        cursor = await self.db._connection.execute(
            "SELECT COUNT(DISTINCT vocabulary_id) FROM user_progress WHERE times_seen > 0"
        )
        learned_count = (await cursor.fetchone())[0]
        
        return {
            "total_vocabulary": total_count,
            "learned_vocabulary": learned_count,
            "new_vocabulary": total_count - learned_count,
            "hsk_level_counts": hsk_counts,
            "word_type_counts": type_counts
        }
    
    async def get_random_vocabulary(
        self,
        count: int = 5,
        hsk_level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get random vocab items.
        
        Args:
            count: Number of words to return
            hsk_level: Optional HSK level filter
        
        Returns:
            List of random vocab items
        """
        if hsk_level:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                WHERE hsk_level = ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (hsk_level, count)
            )
        else:
            cursor = await self.db._connection.execute(
                """
                SELECT * FROM vocabulary
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (count,)
            )
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    def format_vocabulary_for_display(
        self,
        vocab_list: List[Dict[str, Any]],
        include_progress: bool = False
    ) -> str:
        """
        Format vocab list for display to user.
        
        Args:
            vocab_list: List of vocab dictionaries
            include_progress: Whether to include progress information
        
        Returns:
            Formatted string for display
        """
        if not vocab_list:
            return "No vocabulary found."
        
        output = []
        
        for i, vocab in enumerate(vocab_list, 1):
            line = f"**{i}. {vocab['chinese']}** ({vocab['pinyin']})"
            line += f"\n   📖 {vocab['english']}"
            
            if vocab.get('word_type'):
                line += f" · {vocab['word_type']}"
            
            if include_progress and 'mastery_level' in vocab:
                mastery = vocab['mastery_level']
                mastery_emoji = ["🔴", "🟠", "🟡", "🟢", "🔵", "⭐"][mastery]
                line += f"\n   {mastery_emoji} Mastery: {mastery}/5"
                
                if vocab.get('times_seen'):
                    accuracy = (vocab.get('times_correct', 0) / vocab['times_seen'] * 100)
                    line += f" | Seen: {vocab['times_seen']}x | Accuracy: {accuracy:.0f}%"
            
            if vocab.get('example_sentence'):
                line += f"\n   💬 Example: {vocab['example_sentence']}"
            
            output.append(line)
        
        return "\n\n".join(output)