"""YouTube Data API fetcher for videos, transcripts, and comments."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import sys
import os
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


class YouTubeFetcher:
    """
    Fetches YouTube data using YouTube Data API v3.
    
    Features:
    - Search for videos by politician name
    - Get trending/popular videos
    - Extract video transcripts
    - Get video comments
    """
    
    def __init__(self):
        self.api_key = settings.youtube_api_key
        self.youtube = None
        
        if self.api_key:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            except Exception as e:
                print(f"YouTube API initialization error: {e}")
    
    def is_available(self) -> bool:
        """Check if YouTube API is configured."""
        return self.youtube is not None
    
    def search_videos(
        self,
        query: str,
        max_results: int = 10,
        order: str = "viewCount",  # viewCount, relevance, date, rating
        published_after: Optional[str] = None
    ) -> dict:
        """
        Search for videos about a politician.
        
        Args:
            query: Search query (politician name)
            max_results: Maximum number of videos to return
            order: Sort order (viewCount for most viewed, relevance for best match)
            published_after: ISO 8601 date (e.g., "2024-01-01T00:00:00Z")
            
        Returns:
            Dict with videos list and metadata
        """
        if not self.is_available():
            return {
                "videos": [],
                "total_results": 0,
                "error": "YouTube API not configured. Set YOUTUBE_API_KEY"
            }
        
        try:
            # Build search query - add India/politics context
            search_query = f"{query} India politics"
            
            request_params = {
                'part': 'snippet',  # Search API only supports snippet
                'q': search_query,
                'type': 'video',
                'maxResults': min(max_results, 50),
                'order': order,
                'relevanceLanguage': 'en',
                'regionCode': 'IN'  # India region
            }
            
            if published_after:
                request_params['publishedAfter'] = published_after
            
            # Execute search
            search_response = self.youtube.search().list(**request_params).execute()
            
            videos = []
            video_ids = []
            
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                video_ids.append(video_id)
                
                videos.append({
                    "video_id": video_id,
                    "title": item['snippet']['title'],
                    "description": item['snippet']['description'][:500],
                    "channel": item['snippet']['channelTitle'],
                    "published_at": item['snippet']['publishedAt'],
                    "thumbnail": item['snippet']['thumbnails']['high']['url'],
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
            
            # Get detailed statistics for videos
            if video_ids:
                stats_response = self.youtube.videos().list(
                    part='statistics,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                stats_dict = {
                    item['id']: item for item in stats_response.get('items', [])
                }
                
                # Add statistics to videos
                for video in videos:
                    vid_id = video['video_id']
                    if vid_id in stats_dict:
                        stats = stats_dict[vid_id].get('statistics', {})
                        video['views'] = int(stats.get('viewCount', 0))
                        video['likes'] = int(stats.get('likeCount', 0))
                        video['comments_count'] = int(stats.get('commentCount', 0))
                        video['duration'] = stats_dict[vid_id].get('contentDetails', {}).get('duration', '')
            
            # Sort by views if not already sorted
            if order != 'viewCount':
                videos.sort(key=lambda x: x.get('views', 0), reverse=True)
            
            return {
                "videos": videos,
                "total_results": len(videos),
                "error": None
            }
            
        except HttpError as e:
            return {
                "videos": [],
                "total_results": 0,
                "error": f"YouTube API error: {e.resp.status} - {e.error_details}"
            }
        except Exception as e:
            return {
                "videos": [],
                "total_results": 0,
                "error": f"YouTube error: {str(e)}"
            }
    
    def get_trending_videos(
        self,
        query: str,
        max_results: int = 10,
        days_back: int = 30
    ) -> dict:
        """
        Get trending videos (most viewed in recent period).
        
        Args:
            query: Politician name
            max_results: Maximum videos to return
            days_back: How many days back to search
        """
        published_after = (datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'
        
        return self.search_videos(
            query=query,
            max_results=max_results,
            order="viewCount",
            published_after=published_after
        )
    
    def get_transcript(self, video_id: str) -> dict:
        """
        Get transcript/captions for a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Dict with transcript text and metadata
        """
        if not self.is_available():
            return {
                "transcript": "",
                "error": "YouTube API not configured"
            }
        
        try:
            # Try to get transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'hi'])
            
            # Combine all transcript segments
            transcript_text = ' '.join([item['text'] for item in transcript_list])
            
            return {
                "transcript": transcript_text,
                "segments": transcript_list,
                "error": None
            }
            
        except TranscriptsDisabled:
            return {
                "transcript": "",
                "error": "Transcripts disabled for this video"
            }
        except NoTranscriptFound:
            return {
                "transcript": "",
                "error": "No transcript found for this video"
            }
        except Exception as e:
            return {
                "transcript": "",
                "error": f"Transcript error: {str(e)}"
            }
    
    def get_video_comments(
        self,
        video_id: str,
        max_comments: int = 100
    ) -> dict:
        """
        Get comments for a video.
        
        Args:
            video_id: YouTube video ID
            max_comments: Maximum comments to fetch
            
        Returns:
            Dict with comments list and metadata
        """
        if not self.is_available():
            return {
                "comments": [],
                "total_results": 0,
                "error": "YouTube API not configured"
            }
        
        try:
            comments = []
            next_page_token = None
            
            # YouTube API returns 100 comments per page max
            while len(comments) < max_comments:
                request_params = {
                    'part': 'snippet',
                    'videoId': video_id,
                    'maxResults': min(100, max_comments - len(comments)),
                    'order': 'relevance',  # Most relevant first
                    'textFormat': 'plainText'
                }
                
                if next_page_token:
                    request_params['pageToken'] = next_page_token
                
                response = self.youtube.commentThreads().list(**request_params).execute()
                
                for item in response.get('items', []):
                    comment = item['snippet']['topLevelComment']['snippet']
                    comments.append({
                        "text": comment['textDisplay'],
                        "author": comment['authorDisplayName'],
                        "likes": comment.get('likeCount', 0),
                        "published_at": comment['publishedAt'],
                        "updated_at": comment.get('updatedAt', comment['publishedAt'])
                    })
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
            
            return {
                "comments": comments[:max_comments],
                "total_results": len(comments),
                "error": None
            }
            
        except HttpError as e:
            return {
                "comments": [],
                "total_results": 0,
                "error": f"YouTube API error: {e.resp.status}"
            }
        except Exception as e:
            return {
                "comments": [],
                "total_results": 0,
                "error": f"Comments error: {str(e)}"
            }
    
    def get_comprehensive_data(
        self,
        politician_name: str,
        max_videos: int = 5,
        max_comments_per_video: int = 50
    ) -> dict:
        """
        Get comprehensive YouTube data: videos, transcripts, and comments.
        
        Args:
            politician_name: Name of politician
            max_videos: Maximum videos to analyze
            max_comments_per_video: Comments per video
            
        Returns:
            Comprehensive data dict
        """
        # Get trending videos
        videos_data = self.get_trending_videos(politician_name, max_results=max_videos)
        
        if videos_data.get("error") or not videos_data.get("videos"):
            return videos_data
        
        videos = videos_data["videos"]
        
        # Get transcripts and comments for each video
        for video in videos:
            video_id = video['video_id']
            
            # Get transcript
            transcript_data = self.get_transcript(video_id)
            video['transcript'] = transcript_data.get('transcript', '')
            video['transcript_error'] = transcript_data.get('error')
            
            # Get comments
            comments_data = self.get_video_comments(video_id, max_comments_per_video)
            video['comments'] = comments_data.get('comments', [])
            video['comments_error'] = comments_data.get('error')
        
        return {
            "videos": videos,
            "total_results": len(videos),
            "error": None
        }


# Module-level instance
youtube_fetcher = YouTubeFetcher()

