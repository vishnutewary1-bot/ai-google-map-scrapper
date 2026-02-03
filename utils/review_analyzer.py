"""Enhanced review analysis with keyword extraction and trends.

This module analyzes reviews to extract:
- Common keywords/topics
- Sentiment trends over time
- Owner response rate
- Highlighted phrases
"""

import re
from typing import Dict, List, Optional
from collections import Counter
from datetime import datetime
from loguru import logger


class ReviewAnalyzer:
    """
    Analyzes reviews to extract:
    - Common keywords/topics
    - Sentiment trends over time
    - Owner response rate
    - Highlighted phrases
    """

    # Positive indicator words
    POSITIVE_WORDS = {
        'excellent', 'amazing', 'great', 'wonderful', 'fantastic', 'best',
        'friendly', 'helpful', 'professional', 'quick', 'clean', 'delicious',
        'recommend', 'love', 'awesome', 'perfect', 'outstanding', 'incredible',
        'superb', 'brilliant', 'exceptional', 'pleasant', 'satisfied', 'happy',
        'impressed', 'quality', 'efficient', 'reliable', 'trustworthy', 'polite',
        'attentive', 'courteous', 'knowledgeable', 'skilled', 'talented', 'expert',
        'fresh', 'tasty', 'beautiful', 'comfortable', 'convenient', 'fast',
        'prompt', 'responsive', 'caring', 'thorough', 'dedicated', 'genuine'
    }

    # Negative indicator words
    NEGATIVE_WORDS = {
        'terrible', 'awful', 'worst', 'bad', 'poor', 'horrible', 'rude',
        'slow', 'dirty', 'expensive', 'disappointing', 'avoid', 'never',
        'unprofessional', 'waste', 'overpriced', 'disgusting', 'incompetent',
        'useless', 'pathetic', 'ridiculous', 'unacceptable', 'frustrating',
        'annoying', 'unhelpful', 'disrespectful', 'careless', 'sloppy',
        'mediocre', 'boring', 'bland', 'cold', 'stale', 'broken', 'damaged',
        'scam', 'fraud', 'fake', 'cheated', 'ignored', 'waited', 'delayed',
        'mistake', 'error', 'wrong', 'failed', 'problem', 'issue', 'complaint'
    }

    # Common stop words to exclude from keyword extraction
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
        'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'up',
        'about', 'into', 'over', 'after', 'and', 'but', 'or', 'not', 'very',
        'just', 'also', 'only', 'here', 'there', 'then', 'than', 'so', 'as',
        'if', 'my', 'your', 'their', 'our', 'its', 'me', 'him', 'her', 'us',
        'them', 'been', 'being', 'get', 'got', 'go', 'went', 'come', 'came',
        'really', 'always', 'every', 'all', 'some', 'any', 'no', 'more', 'most',
        'other', 'same', 'such', 'own', 'back', 'again', 'still', 'even', 'well'
    }

    def __init__(self):
        pass

    def extract_keywords(self, reviews: List[Dict], top_n: int = 10) -> List[Dict]:
        """
        Extract most common meaningful keywords from reviews.

        Args:
            reviews: List of review dictionaries with 'text' and optionally 'rating'
            top_n: Number of top keywords to return

        Returns:
            List of dicts with 'keyword', 'count', 'sentiment' keys
        """
        word_counts = Counter()
        word_sentiment = {}

        for review in reviews:
            text = (review.get('text') or review.get('review_text') or '').lower()
            rating = review.get('rating') or review.get('stars') or 3

            # Extract words (at least 3 characters)
            words = re.findall(r'\b[a-z]{3,}\b', text)

            for word in words:
                if word not in self.STOP_WORDS:
                    word_counts[word] += 1

                    # Track sentiment association
                    if word not in word_sentiment:
                        word_sentiment[word] = {'positive': 0, 'negative': 0, 'neutral': 0}

                    if rating >= 4:
                        word_sentiment[word]['positive'] += 1
                    elif rating <= 2:
                        word_sentiment[word]['negative'] += 1
                    else:
                        word_sentiment[word]['neutral'] += 1

        # Get top keywords
        keywords = []
        for word, count in word_counts.most_common(top_n * 2):  # Get more to filter
            sentiment = word_sentiment.get(word, {})
            pos = sentiment.get('positive', 0)
            neg = sentiment.get('negative', 0)
            neutral = sentiment.get('neutral', 0)

            # Determine sentiment label
            if pos > neg * 2:
                sent_label = 'positive'
            elif neg > pos * 2:
                sent_label = 'negative'
            else:
                sent_label = 'neutral'

            # Check if it's a known sentiment word
            is_positive_word = word in self.POSITIVE_WORDS
            is_negative_word = word in self.NEGATIVE_WORDS

            keywords.append({
                'keyword': word,
                'count': count,
                'sentiment': sent_label,
                'is_positive_word': is_positive_word,
                'is_negative_word': is_negative_word,
                'positive_reviews': pos,
                'negative_reviews': neg
            })

        return keywords[:top_n]

    def analyze_trends(self, reviews: List[Dict]) -> Dict:
        """
        Analyze rating trends over time.

        Args:
            reviews: List of review dicts with 'rating' and optionally 'date'

        Returns:
            Trend data including direction and momentum
        """
        if not reviews or len(reviews) < 3:
            return {
                'trend': 'insufficient_data',
                'momentum': 0,
                'early_average': 0,
                'recent_average': 0,
                'total_reviews': len(reviews) if reviews else 0
            }

        # Get reviews with ratings
        rated_reviews = [
            r for r in reviews
            if r.get('rating') or r.get('stars')
        ]

        if len(rated_reviews) < 3:
            return {
                'trend': 'insufficient_data',
                'momentum': 0,
                'early_average': 0,
                'recent_average': 0,
                'total_reviews': len(rated_reviews)
            }

        # Simple trend: compare first half vs second half average
        mid = len(rated_reviews) // 2
        first_half = rated_reviews[:mid]
        second_half = rated_reviews[mid:]

        first_half_avg = sum(
            r.get('rating') or r.get('stars') or 0
            for r in first_half
        ) / len(first_half)

        second_half_avg = sum(
            r.get('rating') or r.get('stars') or 0
            for r in second_half
        ) / len(second_half)

        diff = second_half_avg - first_half_avg

        if diff > 0.3:
            trend = 'improving'
        elif diff < -0.3:
            trend = 'declining'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'momentum': round(diff, 2),
            'early_average': round(first_half_avg, 2),
            'recent_average': round(second_half_avg, 2),
            'total_reviews': len(rated_reviews),
            'direction': 'up' if diff > 0 else 'down' if diff < 0 else 'flat'
        }

    def calculate_response_rate(self, reviews: List[Dict]) -> Dict:
        """
        Calculate owner response rate to reviews.

        Args:
            reviews: List of review dicts with optional 'owner_response'

        Returns:
            Dict with response_rate, total_reviews, responses, engagement_level
        """
        total = len(reviews)
        responded = sum(
            1 for r in reviews
            if r.get('owner_response') or r.get('response') or r.get('has_response')
        )

        if total == 0:
            return {
                'response_rate': 0,
                'total_reviews': 0,
                'responses': 0,
                'engagement_level': 'none'
            }

        rate = responded / total

        if rate > 0.5:
            engagement = 'high'
        elif rate > 0.2:
            engagement = 'medium'
        elif rate > 0:
            engagement = 'low'
        else:
            engagement = 'none'

        return {
            'response_rate': round(rate * 100, 1),
            'total_reviews': total,
            'responses': responded,
            'engagement_level': engagement
        }

    def extract_highlights(self, reviews: List[Dict], max_highlights: int = 5) -> List[str]:
        """
        Extract notable phrases/sentences from positive reviews.

        Args:
            reviews: List of review dicts
            max_highlights: Maximum number of highlights to return

        Returns:
            List of highlight strings
        """
        highlights = []

        for review in reviews:
            rating = review.get('rating') or review.get('stars') or 3
            if rating >= 4:
                text = review.get('text') or review.get('review_text') or ''
                sentences = re.split(r'[.!?]', text)

                for sentence in sentences:
                    sentence = sentence.strip()
                    if 20 < len(sentence) < 150:
                        # Check for positive indicators
                        lower = sentence.lower()
                        if any(w in lower for w in self.POSITIVE_WORDS):
                            highlights.append(sentence)

        # Return unique highlights
        seen = set()
        unique = []
        for h in highlights:
            h_lower = h.lower()
            if h_lower not in seen:
                seen.add(h_lower)
                unique.append(h)

        return unique[:max_highlights]

    def calculate_rating_distribution(self, reviews: List[Dict]) -> Dict:
        """
        Calculate the distribution of ratings.

        Args:
            reviews: List of review dicts with 'rating'

        Returns:
            Dict with star distribution and percentages
        """
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for review in reviews:
            rating = review.get('rating') or review.get('stars')
            if rating and 1 <= rating <= 5:
                distribution[int(rating)] += 1

        total = sum(distribution.values())

        return {
            '5_star': distribution[5],
            '4_star': distribution[4],
            '3_star': distribution[3],
            '2_star': distribution[2],
            '1_star': distribution[1],
            'total': total,
            '5_star_pct': round(distribution[5] / total * 100, 1) if total > 0 else 0,
            '4_star_pct': round(distribution[4] / total * 100, 1) if total > 0 else 0,
            '3_star_pct': round(distribution[3] / total * 100, 1) if total > 0 else 0,
            '2_star_pct': round(distribution[2] / total * 100, 1) if total > 0 else 0,
            '1_star_pct': round(distribution[1] / total * 100, 1) if total > 0 else 0,
            'positive_pct': round((distribution[4] + distribution[5]) / total * 100, 1) if total > 0 else 0,
            'negative_pct': round((distribution[1] + distribution[2]) / total * 100, 1) if total > 0 else 0,
        }

    def full_analysis(self, reviews: List[Dict]) -> Dict:
        """
        Perform complete review analysis.

        Args:
            reviews: List of review dictionaries

        Returns:
            Dict with complete analysis results
        """
        if not reviews:
            return {
                'total_reviews': 0,
                'average_rating': 0,
                'rating_distribution': {},
                'keywords': [],
                'trends': {'trend': 'no_data', 'momentum': 0},
                'response_rate': {'response_rate': 0, 'engagement_level': 'none'},
                'highlights': [],
                'sentiment_summary': 'no_data'
            }

        # Calculate average rating
        ratings = [
            r.get('rating') or r.get('stars')
            for r in reviews
            if r.get('rating') or r.get('stars')
        ]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        # Get keywords
        keywords = self.extract_keywords(reviews)

        # Determine overall sentiment
        positive_keywords = sum(1 for k in keywords if k['sentiment'] == 'positive')
        negative_keywords = sum(1 for k in keywords if k['sentiment'] == 'negative')

        if avg_rating >= 4.0 or positive_keywords > negative_keywords * 2:
            sentiment_summary = 'mostly_positive'
        elif avg_rating <= 2.5 or negative_keywords > positive_keywords * 2:
            sentiment_summary = 'mostly_negative'
        else:
            sentiment_summary = 'mixed'

        return {
            'total_reviews': len(reviews),
            'average_rating': round(avg_rating, 2),
            'rating_distribution': self.calculate_rating_distribution(reviews),
            'keywords': keywords,
            'trends': self.analyze_trends(reviews),
            'response_rate': self.calculate_response_rate(reviews),
            'highlights': self.extract_highlights(reviews),
            'sentiment_summary': sentiment_summary
        }


# Convenience functions
def analyze_reviews(reviews: List[Dict]) -> Dict:
    """
    Quick function to analyze reviews.

    Args:
        reviews: List of review dictionaries

    Returns:
        Dict with complete analysis results
    """
    analyzer = ReviewAnalyzer()
    return analyzer.full_analysis(reviews)


def extract_review_keywords(reviews: List[Dict], top_n: int = 10) -> List[Dict]:
    """
    Extract top keywords from reviews.

    Args:
        reviews: List of review dictionaries
        top_n: Number of keywords to return

    Returns:
        List of keyword dicts
    """
    analyzer = ReviewAnalyzer()
    return analyzer.extract_keywords(reviews, top_n)


def get_review_highlights(reviews: List[Dict], max_highlights: int = 5) -> List[str]:
    """
    Get notable review highlights.

    Args:
        reviews: List of review dictionaries
        max_highlights: Maximum highlights to return

    Returns:
        List of highlight strings
    """
    analyzer = ReviewAnalyzer()
    return analyzer.extract_highlights(reviews, max_highlights)


# Alias for backward compatibility
ReviewAnalysisEngine = ReviewAnalyzer
