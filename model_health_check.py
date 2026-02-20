#!/usr/bin/env python3
"""OpenRouter Free Model Health Checker

Fetches all free models from OpenRouter and tests their availability
by sending a simple completion request to each.

Usage:
    python model_health_check.py [--timeout SECONDS] [--parallel N] [--output FILE]

Environment:
    OPENROUTER_API_KEY: Your OpenRouter API key (or set in .env)
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# Load environment variables
load_dotenv()

console = Console()

# Configuration
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_TIMEOUT = 30  # seconds per model test
MAX_PARALLEL = 5  # concurrent tests


@dataclass
class ModelInfo:
    """Information about a model."""
    id: str
    name: str
    context_length: int = 0
    pricing_prompt: str = "0"
    pricing_completion: str = "0"
    
    @property
    def is_free(self) -> bool:
        """Check if model is free (zero cost)."""
        try:
            prompt_cost = float(self.pricing_prompt)
            completion_cost = float(self.pricing_completion)
            return prompt_cost == 0 and completion_cost == 0
        except (ValueError, TypeError):
            return False


@dataclass
class HealthCheckResult:
    """Result of a model health check."""
    model_id: str
    model_name: str
    status: str  # "healthy", "unhealthy", "error", "timeout", "rate_limited", "bad_response"
    response_time_ms: float = 0
    error_message: str = ""
    tokens_used: int = 0
    response_text: str = ""  # Actual model response
    response_quality: str = ""  # "good", "empty", "gibberish", "error"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class OpenRouterHealthChecker:
    """Health checker for OpenRouter free models."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        max_parallel: int = MAX_PARALLEL,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_parallel = max_parallel
        self.results: list[HealthCheckResult] = []
        
    def _get_headers(self) -> dict[str, str]:
        """Get request headers with auth."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/froq-health-checker",
            "X-Title": "Froq Model Health Checker",
        }
    
    async def fetch_models(self) -> list[ModelInfo]:
        """Fetch all available models from OpenRouter."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model_data in data.get("data", []):
                pricing = model_data.get("pricing", {})
                models.append(ModelInfo(
                    id=model_data.get("id", ""),
                    name=model_data.get("name", model_data.get("id", "Unknown")),
                    context_length=model_data.get("context_length", 0),
                    pricing_prompt=str(pricing.get("prompt", "0")),
                    pricing_completion=str(pricing.get("completion", "0")),
                ))
            
            return models
    
    async def get_free_models(self) -> list[ModelInfo]:
        """Get only free models."""
        all_models = await self.fetch_models()
        return [m for m in all_models if m.is_free]
    
    def _validate_response(self, response_text: str) -> tuple[str, str]:
        """Validate response quality.
        
        Returns:
            Tuple of (quality, reason) where quality is 'good', 'empty', 'gibberish', or 'error'
        """
        if not response_text or not response_text.strip():
            return "empty", "No response text"
        
        text = response_text.strip()
        
        # Check for minimum meaningful length
        if len(text) < 5:
            return "empty", "Response too short"
        
        # Check for error messages in response
        error_indicators = ["error", "failed", "unavailable", "not available", "rate limit"]
        text_lower = text.lower()
        for indicator in error_indicators:
            if indicator in text_lower and len(text) < 100:
                return "error", f"Response indicates error: {text[:50]}"
        
        # Check for gibberish (repeating characters, no words)
        # Simple heuristic: should have some common words or patterns
        words = text.split()
        if len(words) < 2:
            # Single word responses might be OK for simple tests
            if len(text) > 50:  # Long single "word" is suspicious
                return "gibberish", "Response appears to be gibberish"
        
        # Check for excessive repetition
        if len(text) > 20:
            unique_chars = len(set(text.lower()))
            if unique_chars < 5:  # Very few unique characters
                return "gibberish", "Response has excessive repetition"
        
        return "good", ""
    
    async def test_model(self, model: ModelInfo) -> HealthCheckResult:
        """Test a single model with a conversational completion request."""
        start_time = time.time()
        
        # Use a natural conversational test prompt
        test_prompt = "Hi, how are you doing today? Please respond briefly."
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json={
                        "model": model.id,
                        "messages": [
                            {"role": "user", "content": test_prompt}
                        ],
                        "max_tokens": 100,  # Allow reasonable response length
                        "temperature": 0.7,  # Some creativity for natural response
                    },
                )
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    
                    # Extract response text
                    choices = data.get("choices", [])
                    response_text = ""
                    if choices:
                        message = choices[0].get("message", {})
                        response_text = message.get("content", "")
                    
                    # Validate response quality
                    quality, quality_reason = self._validate_response(response_text)
                    
                    if quality == "good":
                        return HealthCheckResult(
                            model_id=model.id,
                            model_name=model.name,
                            status="healthy",
                            response_time_ms=elapsed_ms,
                            tokens_used=usage.get("total_tokens", 0),
                            response_text=response_text[:200],  # Truncate for storage
                            response_quality=quality,
                        )
                    else:
                        return HealthCheckResult(
                            model_id=model.id,
                            model_name=model.name,
                            status="bad_response",
                            response_time_ms=elapsed_ms,
                            tokens_used=usage.get("total_tokens", 0),
                            response_text=response_text[:200],
                            response_quality=quality,
                            error_message=quality_reason,
                        )
                        
                elif response.status_code == 429:
                    return HealthCheckResult(
                        model_id=model.id,
                        model_name=model.name,
                        status="rate_limited",
                        response_time_ms=elapsed_ms,
                        error_message="Rate limit exceeded",
                    )
                else:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get("error", {}).get("message", response.text[:200])
                    return HealthCheckResult(
                        model_id=model.id,
                        model_name=model.name,
                        status="unhealthy",
                        response_time_ms=elapsed_ms,
                        error_message=error_msg,
                    )
                    
        except httpx.TimeoutException:
            return HealthCheckResult(
                model_id=model.id,
                model_name=model.name,
                status="timeout",
                response_time_ms=self.timeout * 1000,
                error_message=f"Request timed out after {self.timeout}s",
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                model_id=model.id,
                model_name=model.name,
                status="error",
                response_time_ms=elapsed_ms,
                error_message=str(e),
            )
    
    async def run_health_check(
        self,
        models: list[ModelInfo] | None = None,
        progress_callback: callable = None,
    ) -> list[HealthCheckResult]:
        """Run health checks on all free models."""
        if models is None:
            models = await self.get_free_models()
        
        self.results = []
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def check_with_semaphore(model: ModelInfo) -> HealthCheckResult:
            async with semaphore:
                result = await self.test_model(model)
                self.results.append(result)
                if progress_callback:
                    progress_callback(result)
                return result
        
        tasks = [check_with_semaphore(model) for model in models]
        await asyncio.gather(*tasks)
        
        return self.results
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of health check results."""
        total = len(self.results)
        healthy = sum(1 for r in self.results if r.status == "healthy")
        bad_response = sum(1 for r in self.results if r.status == "bad_response")
        unhealthy = sum(1 for r in self.results if r.status == "unhealthy")
        timeout = sum(1 for r in self.results if r.status == "timeout")
        rate_limited = sum(1 for r in self.results if r.status == "rate_limited")
        errors = sum(1 for r in self.results if r.status == "error")
        
        healthy_models = [r.model_id for r in self.results if r.status == "healthy"]
        avg_response_time = (
            sum(r.response_time_ms for r in self.results if r.status == "healthy") / healthy
            if healthy > 0 else 0
        )
        
        return {
            "total_models": total,
            "healthy": healthy,
            "bad_response": bad_response,
            "unhealthy": unhealthy,
            "timeout": timeout,
            "rate_limited": rate_limited,
            "errors": errors,
            "healthy_models": healthy_models,
            "average_response_time_ms": round(avg_response_time, 2),
            "timestamp": datetime.now().isoformat(),
        }


def create_results_table(results: list[HealthCheckResult]) -> Table:
    """Create a rich table from health check results."""
    table = Table(title="OpenRouter Free Model Health Check Results", show_lines=True)
    
    table.add_column("Status", justify="center", width=10)
    table.add_column("Model ID", style="cyan", max_width=45)
    table.add_column("Response Time", justify="right", width=12)
    table.add_column("Error / Notes", style="dim", max_width=40)
    
    status_icons = {
        "healthy": ("✅", "green"),
        "bad_response": ("⚠️", "yellow"),
        "unhealthy": ("❌", "red"),
        "timeout": ("⏱️", "yellow"),
        "rate_limited": ("🚫", "yellow"),
        "error": ("💥", "red"),
    }
    
    # Sort: healthy first, then by response time
    sorted_results = sorted(
        results,
        key=lambda r: (0 if r.status == "healthy" else 1, r.response_time_ms),
    )
    
    for result in sorted_results:
        icon, color = status_icons.get(result.status, ("❓", "white"))
        status_text = Text(f"{icon} {result.status}", style=color)
        
        time_text = f"{result.response_time_ms:.0f}ms"
        if result.response_time_ms < 1000:
            time_style = "green"
        elif result.response_time_ms < 3000:
            time_style = "yellow"
        else:
            time_style = "red"
        
        error_text = result.error_message[:40] + "..." if len(result.error_message) > 40 else result.error_message
        
        table.add_row(
            status_text,
            result.model_id,
            Text(time_text, style=time_style),
            error_text,
        )
    
    return table


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenRouter Free Model Health Checker")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout per model (seconds)")
    parser.add_argument("--parallel", type=int, default=MAX_PARALLEL, help="Max parallel requests")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--quiet", action="store_true", help="Minimal output (just summary)")
    args = parser.parse_args()
    
    if not OPENROUTER_API_KEY:
        console.print("[red]❌ Error: OPENROUTER_API_KEY not set![/red]")
        console.print("Set it in your .env file or as an environment variable.")
        sys.exit(1)
    
    checker = OpenRouterHealthChecker(
        api_key=OPENROUTER_API_KEY,
        timeout=args.timeout,
        max_parallel=args.parallel,
    )
    
    # Fetch free models
    console.print(Panel("🔍 Fetching free models from OpenRouter...", style="cyan"))
    
    try:
        free_models = await checker.get_free_models()
    except Exception as e:
        console.print(f"[red]❌ Failed to fetch models: {e}[/red]")
        sys.exit(1)
    
    console.print(f"[green]✅ Found {len(free_models)} free models[/green]\n")
    
    if not free_models:
        console.print("[yellow]⚠️ No free models found![/yellow]")
        sys.exit(0)
    
    # Run health checks with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Testing models...", total=len(free_models))
        
        def on_progress(result: HealthCheckResult):
            status_icon = "✅" if result.status == "healthy" else "❌"
            progress.update(task, advance=1, description=f"{status_icon} {result.model_id[:30]}")
        
        results = await checker.run_health_check(free_models, progress_callback=on_progress)
    
    # Display results
    if not args.quiet:
        console.print()
        console.print(create_results_table(results))
    
    # Summary
    summary = checker.get_summary()
    
    summary_text = Text()
    summary_text.append("\n📊 Summary\n", style="bold")
    summary_text.append(f"  Total Models Tested: {summary['total_models']}\n")
    summary_text.append(f"  ✅ Healthy: {summary['healthy']}\n", style="green")
    summary_text.append(f"  ⚠️ Bad Response: {summary['bad_response']}\n", style="yellow")
    summary_text.append(f"  ❌ Unhealthy: {summary['unhealthy']}\n", style="red")
    summary_text.append(f"  ⏱️ Timeout: {summary['timeout']}\n", style="yellow")
    summary_text.append(f"  🚫 Rate Limited: {summary['rate_limited']}\n", style="yellow")
    summary_text.append(f"  💥 Errors: {summary['errors']}\n", style="red")
    summary_text.append(f"  ⚡ Avg Response Time: {summary['average_response_time_ms']}ms\n")
    
    console.print(Panel(summary_text, title="Health Check Complete", border_style="green"))
    
    # Output healthy models
    if summary['healthy'] > 0:
        console.print("\n[bold green]🎉 Available Free Models:[/bold green]")
        for model_id in summary['healthy_models'][:20]:  # Show top 20
            console.print(f"  • {model_id}")
        if len(summary['healthy_models']) > 20:
            console.print(f"  ... and {len(summary['healthy_models']) - 20} more")
    
    # Save to file if requested
    if args.output:
        output_data = {
            "summary": summary,
            "results": [
                {
                    "model_id": r.model_id,
                    "model_name": r.model_name,
                    "status": r.status,
                    "response_quality": r.response_quality,
                    "response_time_ms": r.response_time_ms,
                    "response_text": r.response_text,
                    "error_message": r.error_message,
                    "timestamp": r.timestamp,
                }
                for r in results
            ],
        }
        
        output_path = Path(args.output)
        output_path.write_text(json.dumps(output_data, indent=2))
        console.print(f"\n[dim]Results saved to: {output_path}[/dim]")
    
    return 0 if summary['healthy'] > 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
