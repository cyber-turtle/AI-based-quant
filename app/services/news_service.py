"""
NEWS SERVICE - Economic Calendar & High Impact Event Filter
Ported from backend/src/services/news.service.ts
Uses ForexFactory JSON feed for event detection.
"""
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CalendarEvent:
    title: str
    country: str
    date: str
    impact: str
    forecast: str
    previous: str

class NewsService:
    """
    Fetches economic calendar events and provides trading halt signals.
    """
    
    def __init__(self):
        self.calendar_url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.cache: List[CalendarEvent] = []
        self.cache_expires: Optional[datetime] = None
        self.cache_ttl_minutes = 5
    
    def _fetch_events(self) -> List[CalendarEvent]:
        """Fetch this week's calendar from ForexFactory"""
        # Check cache
        if self.cache and self.cache_expires and datetime.now() < self.cache_expires:
            return self.cache
        
        try:
            logger.info("📰 Fetching news from ForexFactory...")
            response = requests.get(self.calendar_url, timeout=10)
            if response.status_code == 200:
                events = response.json()
                now = datetime.now()
                
                # Filter for events within ±24 hours
                filtered = []
                for e in events:
                    try:
                        event_date = datetime.fromisoformat(e.get('date', '').replace('Z', '+00:00'))
                        if abs((event_date - now).total_seconds()) < 24 * 3600:
                            filtered.append(CalendarEvent(
                                title=e.get('title', ''),
                                country=e.get('country', ''),
                                date=e.get('date', ''),
                                impact=e.get('impact', 'Low'),
                                forecast=e.get('forecast', ''),
                                previous=e.get('previous', '')
                            ))
                    except:
                        pass
                
                self.cache = filtered
                self.cache_expires = datetime.now() + timedelta(minutes=self.cache_ttl_minutes)
                logger.info(f"Loaded {len(filtered)} upcoming news events")
                return filtered
        except Exception as e:
            logger.error(f"Failed to fetch calendar: {e}")
        
        return self.cache if self.cache else []
    
    def check_news_stop(self, symbol: str, buffer_minutes: int = 30) -> Dict:
        """
        Check if trading should be halted due to high-impact news.
        Returns: {stop: bool, reason: str, events: list}
        """
        events = self._fetch_events()
        now = datetime.now()
        buffer = timedelta(minutes=buffer_minutes)
        
        # Extract base and quote currencies
        base = symbol[:3].upper()
        quote = symbol[3:6].upper() if len(symbol) >= 6 else ""
        
        blocking_events = []
        
        for event in events:
            if event.impact != "High":
                continue
            
            # Check if event affects this pair
            if event.country not in [base, quote, "USD"]:
                continue
            
            try:
                event_time = datetime.fromisoformat(event.date.replace('Z', '+00:00'))
                diff = event_time - now
                
                # Block if within buffer before, or 15 mins after
                if timedelta(0) < diff <= buffer:
                    blocking_events.append({
                        "title": event.title,
                        "country": event.country,
                        "minutes_until": int(diff.total_seconds() / 60)
                    })
                elif timedelta(minutes=-15) <= diff <= timedelta(0):
                    blocking_events.append({
                        "title": event.title,
                        "country": event.country,
                        "minutes_ago": int(abs(diff.total_seconds()) / 60)
                    })
            except:
                pass
        
        if blocking_events:
            return {
                "stop": True,
                "reason": f"High Impact: {blocking_events[0]['title']}",
                "events": blocking_events
            }
        
        return {"stop": False, "reason": "", "events": []}
    
    def get_upcoming_events(self, count: int = 10) -> List[Dict]:
        """Get upcoming events for dashboard display"""
        events = self._fetch_events()
        return [
            {
                "title": e.title,
                "country": e.country,
                "impact": e.impact,
                "date": e.date
            }
            for e in events[:count]
        ]

# Singleton
news_service = NewsService()
