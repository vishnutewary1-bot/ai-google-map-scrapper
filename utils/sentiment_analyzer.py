"""Review sentiment analysis using TextBlob."""
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False
    TextBlob = None


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    polarity: float  # -1.0 to 1.0 (negative to positive)
    subjectivity: float  # 0.0 to 1.0 (objective to subjective)
    sentiment: str  # "positive", "negative", "neutral"
    confidence: float  # Confidence score


class SentimentAnalyzer:
    """Analyze sentiment of reviews."""

    def __init__(self):
        self.enabled = HAS_TEXTBLOB
        if not HAS_TEXTBLOB:
            logger.warning("TextBlob not installed. Run: pip install textblob")

    def analyze_text(self, text: str) -> Optional[SentimentResult]:
        """Analyze sentiment of a single text."""
        if not HAS_TEXTBLOB or not text:
            return None

        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity

            # Determine sentiment label
            if polarity > 0.1:
                sentiment = "positive"
            elif polarity < -0.1:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            # Calculate confidence based on polarity strength and subjectivity
            confidence = abs(polarity) * (1 - subjectivity * 0.5)

            return SentimentResult(
                polarity=round(polarity, 3),
                subjectivity=round(subjectivity, 3),
                sentiment=sentiment,
                confidence=round(confidence, 3)
            )
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return None

    def analyze_reviews(self, reviews: List[Dict]) -> Dict:
        """Analyze sentiment of multiple reviews."""
        if not HAS_TEXTBLOB:
            return {"error": "TextBlob not installed", "enabled": False}

        results = {
            "total_analyzed": 0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "average_polarity": 0.0,
            "average_subjectivity": 0.0,
            "sentiment_breakdown": [],
            "key_phrases": {
                "positive": [],
                "negative": []
            },
            "overall_sentiment": "neutral",
            "sentiment_score": 50,  # 0-100 scale
            "enabled": True
        }

        polarities = []
        subjectivities = []

        for review in reviews:
            text = review.get("review_text", "")
            if not text:
                continue

            sentiment_result = self.analyze_text(text)
            if not sentiment_result:
                continue

            results["total_analyzed"] += 1
            polarities.append(sentiment_result.polarity)
            subjectivities.append(sentiment_result.subjectivity)

            if sentiment_result.sentiment == "positive":
                results["positive_count"] += 1
            elif sentiment_result.sentiment == "negative":
                results["negative_count"] += 1
            else:
                results["neutral_count"] += 1

            # Extract key phrases
            self._extract_key_phrases(text, sentiment_result, results)

            results["sentiment_breakdown"].append({
                "review_id": review.get("review_id"),
                "rating": review.get("rating"),
                "polarity": sentiment_result.polarity,
                "subjectivity": sentiment_result.subjectivity,
                "sentiment": sentiment_result.sentiment,
                "confidence": sentiment_result.confidence
            })

        if polarities:
            results["average_polarity"] = round(sum(polarities) / len(polarities), 3)
            results["average_subjectivity"] = round(sum(subjectivities) / len(subjectivities), 3)

            # Determine overall sentiment
            if results["average_polarity"] > 0.2:
                results["overall_sentiment"] = "positive"
            elif results["average_polarity"] < -0.2:
                results["overall_sentiment"] = "negative"
            else:
                results["overall_sentiment"] = "mixed"

            # Calculate 0-100 sentiment score
            results["sentiment_score"] = int((results["average_polarity"] + 1) * 50)

        return results

    def _extract_key_phrases(self, text: str, sentiment: SentimentResult, results: Dict):
        """Extract key phrases from text."""
        if not HAS_TEXTBLOB:
            return

        try:
            blob = TextBlob(text)
            noun_phrases = list(blob.noun_phrases)[:5]  # Top 5 phrases

            category = "positive" if sentiment.sentiment == "positive" else "negative"

            for phrase in noun_phrases:
                if phrase and len(phrase) > 2:
                    if phrase not in results["key_phrases"][category]:
                        results["key_phrases"][category].append(phrase)

                        # Keep only top 10 per category
                        if len(results["key_phrases"][category]) > 10:
                            results["key_phrases"][category] = results["key_phrases"][category][:10]
        except Exception as e:
            logger.debug(f"Key phrase extraction error: {e}")

    def get_sentiment_score(self, reviews: List[Dict]) -> int:
        """Get a simple 0-100 sentiment score for reviews."""
        analysis = self.analyze_reviews(reviews)

        if analysis.get("error") or analysis["total_analyzed"] == 0:
            return 50  # Default neutral

        return analysis["sentiment_score"]

    def analyze_single_review(self, review_text: str, rating: Optional[int] = None) -> Dict:
        """Analyze a single review text."""
        result = self.analyze_text(review_text)

        if not result:
            return {"error": "Could not analyze text", "enabled": HAS_TEXTBLOB}

        analysis = {
            "polarity": result.polarity,
            "subjectivity": result.subjectivity,
            "sentiment": result.sentiment,
            "confidence": result.confidence,
            "sentiment_score": int((result.polarity + 1) * 50),
            "enabled": True
        }

        # Check if sentiment matches rating
        if rating is not None:
            expected_sentiment = "positive" if rating >= 4 else ("negative" if rating <= 2 else "neutral")
            analysis["rating_alignment"] = result.sentiment == expected_sentiment
            analysis["expected_sentiment"] = expected_sentiment

        return analysis

    def get_summary_stats(self, reviews: List[Dict]) -> Dict:
        """Get summary statistics for reviews."""
        analysis = self.analyze_reviews(reviews)

        return {
            "total_reviews": len(reviews),
            "analyzed": analysis.get("total_analyzed", 0),
            "positive_percentage": round(
                (analysis["positive_count"] / max(analysis["total_analyzed"], 1)) * 100, 1
            ),
            "negative_percentage": round(
                (analysis["negative_count"] / max(analysis["total_analyzed"], 1)) * 100, 1
            ),
            "neutral_percentage": round(
                (analysis["neutral_count"] / max(analysis["total_analyzed"], 1)) * 100, 1
            ),
            "overall_sentiment": analysis.get("overall_sentiment", "unknown"),
            "sentiment_score": analysis.get("sentiment_score", 50),
            "top_positive_phrases": analysis["key_phrases"]["positive"][:5],
            "top_negative_phrases": analysis["key_phrases"]["negative"][:5],
        }


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()


def analyze_text(text: str) -> Optional[Dict]:
    """Quick function to analyze text sentiment."""
    result = sentiment_analyzer.analyze_text(text)
    if result:
        return {
            "polarity": result.polarity,
            "subjectivity": result.subjectivity,
            "sentiment": result.sentiment,
            "confidence": result.confidence
        }
    return None
