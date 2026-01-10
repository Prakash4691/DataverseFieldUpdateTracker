"""
Rate limit tracking for Dataverse API operations.

Provides production-grade tracking of API request metrics to monitor and manage
Dataverse service protection limits (6000 requests per 5 minutes per user).
"""

import time
from dataclasses import dataclass, field


@dataclass
class RequestMetrics:
    """Tracks metrics for a single API request."""
    endpoint: str
    timestamp: float
    duration: float
    hit_429: bool = False
    retry_count: int = 0
    retry_after_seconds: int = 0


@dataclass
class RateLimitTracker:
    """
    Production-grade rate limit tracking for Dataverse API calls.
    
    Tracks:
    - Total requests made
    - 429 errors encountered
    - Retry attempts
    - Time spent waiting due to rate limits
    - Requests per 5-minute window
    
    Based on Microsoft Dataverse service protection limits:
    - 6000 requests per 5 minutes per user
    - Evaluated in 5-minute sliding window
    - Must respect Retry-After header
    
    Example:
        >>> tracker = RateLimitTracker()
        >>> ops.get_attibuteid('account', 'name', rate_limit_tracker=tracker)
        >>> tracker.print_summary()
    """
    
    total_requests: int = 0
    total_429_errors: int = 0
    total_retries: int = 0
    total_wait_time: float = 0.0
    request_history: list[RequestMetrics] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def record_request(self, endpoint: str, duration: float, hit_429: bool = False, 
                       retry_count: int = 0, retry_after: int = 0) -> None:
        """
        Record metrics for a completed request.
        
        Args:
            endpoint (str): Description of the API endpoint called.
            duration (float): Time taken for the request in seconds.
            hit_429 (bool): Whether a 429 rate limit error was encountered.
            retry_count (int): Number of retry attempts made.
            retry_after (int): Total seconds waited due to Retry-After headers.
        """
        self.total_requests += 1
        
        if hit_429:
            self.total_429_errors += 1
            self.total_retries += retry_count
            self.total_wait_time += retry_after * retry_count
        
        metric = RequestMetrics(
            endpoint=endpoint,
            timestamp=time.time(),
            duration=duration,
            hit_429=hit_429,
            retry_count=retry_count,
            retry_after_seconds=retry_after
        )
        
        self.request_history.append(metric)
        
        # Keep only last 5 minutes of history for sliding window calculation
        cutoff_time = time.time() - 300  # 5 minutes ago
        self.request_history = [r for r in self.request_history if r.timestamp > cutoff_time]
    
    def get_requests_in_last_5_minutes(self) -> int:
        """
        Get count of requests in the last 5-minute sliding window.
        
        Returns:
            int: Number of requests made in the last 5 minutes.
        """
        cutoff_time = time.time() - 300
        return sum(1 for r in self.request_history if r.timestamp > cutoff_time)
    
    def get_summary(self) -> dict[str, any]:
        """
        Get comprehensive tracking summary.
        
        Returns:
            dict: Summary statistics including request counts, rate limits, and timing.
        """
        elapsed_time = time.time() - self.start_time
        requests_last_5_min = self.get_requests_in_last_5_minutes()
        
        return {
            'total_requests': self.total_requests,
            'total_429_errors': self.total_429_errors,
            'total_retries': self.total_retries,
            'total_wait_time_seconds': round(self.total_wait_time, 2),
            'requests_last_5_minutes': requests_last_5_min,
            'elapsed_time_seconds': round(elapsed_time, 2),
            'average_requests_per_minute': round(self.total_requests / (elapsed_time / 60), 2) if elapsed_time > 0 else 0,
            'rate_limit_percentage': round((requests_last_5_min / 6000) * 100, 2),
            'estimated_time_to_limit': self._estimate_time_to_limit(requests_last_5_min, elapsed_time)
        }
    
    def _estimate_time_to_limit(self, requests_in_window: int, elapsed: float) -> str:
        """
        Estimate time until hitting 6000 request limit.
        
        Args:
            requests_in_window (int): Current requests in 5-minute window.
            elapsed (float): Total elapsed time since tracking started.
        
        Returns:
            str: Human-readable estimate of time until limit.
        """
        if requests_in_window == 0 or elapsed == 0:
            return "N/A"
        
        current_rate = requests_in_window / min(elapsed, 300)  # requests per second
        remaining = 6000 - requests_in_window
        
        if remaining <= 0:
            return "LIMIT REACHED"
        
        if current_rate <= 0:
            return "N/A"
        
        seconds_to_limit = remaining / current_rate
        
        if seconds_to_limit > 300:
            return f">{int(seconds_to_limit/60)} minutes"
        
        return f"{int(seconds_to_limit)} seconds"
    
    def print_summary(self) -> None:
        """Print formatted summary of rate limit tracking to console."""
        summary = self.get_summary()
        
        print("\n" + "=" * 80)
        print("RATE LIMIT TRACKING SUMMARY Applies only for direct API calls")
        print("=" * 80)
        print(f"Total Requests:              {summary['total_requests']}")
        print(f"Requests (Last 5 min):       {summary['requests_last_5_minutes']} / 6000 ({summary['rate_limit_percentage']}%)")
        print(f"429 Errors Encountered:      {summary['total_429_errors']}")
        print(f"Total Retry Attempts:        {summary['total_retries']}")
        print(f"Total Wait Time:             {summary['total_wait_time_seconds']}s")
        print(f"Elapsed Time:                {summary['elapsed_time_seconds']}s")
        print(f"Avg Requests/Minute:         {summary['average_requests_per_minute']}")
        print(f"Est. Time to Limit:          {summary['estimated_time_to_limit']}")
        print("=" * 80)
        
        if summary['total_429_errors'] > 0:
            print("⚠️  Rate limits were encountered. Consider:")
            print("   - Reducing parallelism")
            print("   - Adding delays between requests")
            print("   - Processing in smaller batches")
        elif summary['rate_limit_percentage'] > 80:
            print("⚠️  Approaching rate limit (>80%). Slow down requests.")
        
        print()
