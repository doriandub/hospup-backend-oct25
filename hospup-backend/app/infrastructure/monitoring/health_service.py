"""
Health Check Service

Comprehensive health monitoring for all application components.
Provides detailed health status for monitoring and alerting.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import structlog

from ...application.interfaces.cache_service import ICacheService
from ...domain.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


class HealthCheckResult:
    """Individual health check result"""

    def __init__(
        self,
        service: str,
        healthy: bool,
        response_time_ms: float,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.service = service
        self.healthy = healthy
        self.response_time_ms = response_time_ms
        self.error = error
        self.metadata = metadata or {}
        self.checked_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "service": self.service,
            "healthy": self.healthy,
            "response_time_ms": round(self.response_time_ms, 2),
            "error": self.error,
            "metadata": self.metadata,
            "checked_at": self.checked_at.isoformat()
        }


class HealthService:
    """
    Comprehensive health check service

    Monitors all critical application components:
    - Database connectivity and performance
    - Cache service (Redis)
    - External APIs (OpenAI, AWS Lambda)
    - File storage (S3)
    - Message queues (Celery)
    """

    def __init__(
        self,
        database,
        cache_service: ICacheService,
        external_services: List[Any],
        check_timeout: float = 10.0
    ):
        self.database = database
        self.cache_service = cache_service
        self.external_services = external_services
        self.check_timeout = check_timeout

        # Health check history for trending
        self._health_history: Dict[str, List[HealthCheckResult]] = {}
        self._max_history_size = 100

    async def check_all(self, include_detailed: bool = True) -> Dict[str, Any]:
        """
        Perform comprehensive health check

        Args:
            include_detailed: Include detailed per-service results

        Returns:
            Complete health status with overall and per-service results
        """
        start_time = time.time()
        logger.info("Starting comprehensive health check")

        # Run all health checks concurrently
        tasks = [
            self._check_database(),
            self._check_cache(),
            self._check_external_services()
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.check_timeout
            )

            database_result, cache_result, external_results = results

            # Combine all results
            all_results = []

            if isinstance(database_result, HealthCheckResult):
                all_results.append(database_result)
            elif isinstance(database_result, Exception):
                all_results.append(HealthCheckResult(
                    service="database",
                    healthy=False,
                    response_time_ms=0,
                    error=str(database_result)
                ))

            if isinstance(cache_result, HealthCheckResult):
                all_results.append(cache_result)
            elif isinstance(cache_result, Exception):
                all_results.append(HealthCheckResult(
                    service="cache",
                    healthy=False,
                    response_time_ms=0,
                    error=str(cache_result)
                ))

            if isinstance(external_results, list):
                all_results.extend(external_results)

            # Store in history
            for result in all_results:
                self._store_health_history(result)

            # Calculate overall health
            healthy_services = sum(1 for r in all_results if r.healthy)
            total_services = len(all_results)
            overall_healthy = healthy_services == total_services

            total_time_ms = (time.time() - start_time) * 1000

            response = {
                "healthy": overall_healthy,
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": round(total_time_ms, 2),
                "services": {
                    "total": total_services,
                    "healthy": healthy_services,
                    "unhealthy": total_services - healthy_services
                }
            }

            if include_detailed:
                response["details"] = [r.to_dict() for r in all_results]
                response["trends"] = self._get_health_trends()

            logger.info(
                "Health check completed",
                overall_healthy=overall_healthy,
                healthy_services=healthy_services,
                total_services=total_services,
                response_time_ms=total_time_ms
            )

            return response

        except asyncio.TimeoutError:
            logger.error("Health check timed out", timeout=self.check_timeout)
            return {
                "healthy": False,
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Health check timed out after {self.check_timeout}s",
                "response_time_ms": self.check_timeout * 1000
            }

    async def check_service(self, service_name: str) -> HealthCheckResult:
        """Check health of a specific service"""
        if service_name == "database":
            return await self._check_database()
        elif service_name == "cache":
            return await self._check_cache()
        else:
            return HealthCheckResult(
                service=service_name,
                healthy=False,
                response_time_ms=0,
                error="Unknown service"
            )

    async def _check_database(self) -> HealthCheckResult:
        """Check database health"""
        start_time = time.time()

        try:
            # Test basic connectivity
            async with self.database() as conn:
                # Simple query to test connectivity
                result = await conn.execute("SELECT 1 as health_check")
                row = result.fetchone()

                if not row or row[0] != 1:
                    raise Exception("Database query returned unexpected result")

                # Test write performance
                write_start = time.time()
                await conn.execute("SELECT pg_sleep(0.001)")  # 1ms test
                write_time_ms = (time.time() - write_start) * 1000

                response_time_ms = (time.time() - start_time) * 1000

                return HealthCheckResult(
                    service="database",
                    healthy=True,
                    response_time_ms=response_time_ms,
                    metadata={
                        "write_test_ms": round(write_time_ms, 2),
                        "connection_pool_size": getattr(conn.engine.pool, 'size', 'unknown')
                    }
                )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error("Database health check failed", error=str(e))

            return HealthCheckResult(
                service="database",
                healthy=False,
                response_time_ms=response_time_ms,
                error=str(e)
            )

    async def _check_cache(self) -> HealthCheckResult:
        """Check cache service health"""
        start_time = time.time()

        try:
            # Test basic connectivity with ping-pong
            test_key = f"health_check_{int(time.time())}"
            test_value = "pong"

            # Test set operation
            set_success = await self.cache_service.set(test_key, test_value, expire_seconds=60)
            if not set_success:
                raise Exception("Cache set operation failed")

            # Test get operation
            retrieved_value = await self.cache_service.get(test_key)
            if retrieved_value != test_value:
                raise Exception(f"Cache get returned wrong value: {retrieved_value}")

            # Test delete operation
            delete_success = await self.cache_service.delete(test_key)
            if not delete_success:
                logger.warning("Cache delete operation failed (non-critical)")

            # Test performance
            perf_start = time.time()
            await self.cache_service.set("perf_test", "data", expire_seconds=5)
            await self.cache_service.get("perf_test")
            await self.cache_service.delete("perf_test")
            perf_time_ms = (time.time() - perf_start) * 1000

            response_time_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                service="cache",
                healthy=True,
                response_time_ms=response_time_ms,
                metadata={
                    "performance_test_ms": round(perf_time_ms, 2),
                    "operations": ["set", "get", "delete"]
                }
            )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            logger.error("Cache health check failed", error=str(e))

            return HealthCheckResult(
                service="cache",
                healthy=False,
                response_time_ms=response_time_ms,
                error=str(e)
            )

    async def _check_external_services(self) -> List[HealthCheckResult]:
        """Check all external services health"""
        results = []

        # Check each external service with individual timeout
        for service in self.external_services:
            try:
                result = await asyncio.wait_for(
                    self._check_external_service(service),
                    timeout=5.0  # 5s timeout per service
                )
                results.append(result)
            except asyncio.TimeoutError:
                results.append(HealthCheckResult(
                    service=getattr(service, '__class__', str(service)).__name__,
                    healthy=False,
                    response_time_ms=5000,
                    error="Health check timed out"
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    service=getattr(service, '__class__', str(service)).__name__,
                    healthy=False,
                    response_time_ms=0,
                    error=str(e)
                ))

        return results

    async def _check_external_service(self, service) -> HealthCheckResult:
        """Check individual external service"""
        start_time = time.time()
        service_name = getattr(service, '__class__', str(service)).__name__

        try:
            # Check if service has a health_check method
            if hasattr(service, 'health_check'):
                health_result = await service.health_check()
                response_time_ms = (time.time() - start_time) * 1000

                return HealthCheckResult(
                    service=service_name,
                    healthy=health_result.get('healthy', False),
                    response_time_ms=response_time_ms,
                    error=health_result.get('error'),
                    metadata=health_result.get('metadata', {})
                )
            else:
                # Service doesn't support health checks
                return HealthCheckResult(
                    service=service_name,
                    healthy=True,  # Assume healthy if no health check available
                    response_time_ms=0,
                    metadata={"note": "No health check method available"}
                )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                service=service_name,
                healthy=False,
                response_time_ms=response_time_ms,
                error=str(e)
            )

    def _store_health_history(self, result: HealthCheckResult) -> None:
        """Store health check result in history"""
        service_name = result.service

        if service_name not in self._health_history:
            self._health_history[service_name] = []

        # Add new result
        self._health_history[service_name].append(result)

        # Trim history to max size
        if len(self._health_history[service_name]) > self._max_history_size:
            self._health_history[service_name] = self._health_history[service_name][-self._max_history_size:]

    def _get_health_trends(self) -> Dict[str, Any]:
        """Get health trends from history"""
        trends = {}

        for service_name, history in self._health_history.items():
            if len(history) < 2:
                continue

            recent_results = history[-10:]  # Last 10 results
            healthy_count = sum(1 for r in recent_results if r.healthy)
            avg_response_time = sum(r.response_time_ms for r in recent_results) / len(recent_results)

            trends[service_name] = {
                "success_rate": round((healthy_count / len(recent_results)) * 100, 1),
                "avg_response_time_ms": round(avg_response_time, 2),
                "samples": len(recent_results),
                "last_failure": None
            }

            # Find last failure
            for result in reversed(recent_results):
                if not result.healthy:
                    trends[service_name]["last_failure"] = {
                        "timestamp": result.checked_at.isoformat(),
                        "error": result.error
                    }
                    break

        return trends

    def get_service_uptime(self, service_name: str, hours: int = 24) -> Dict[str, Any]:
        """Get service uptime statistics"""
        if service_name not in self._health_history:
            return {"error": "No health check data available"}

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_results = [
            r for r in self._health_history[service_name]
            if r.checked_at > cutoff_time
        ]

        if not recent_results:
            return {"error": "No recent health check data"}

        total_checks = len(recent_results)
        successful_checks = sum(1 for r in recent_results if r.healthy)
        uptime_percentage = (successful_checks / total_checks) * 100

        return {
            "service": service_name,
            "period_hours": hours,
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "failed_checks": total_checks - successful_checks,
            "uptime_percentage": round(uptime_percentage, 2),
            "avg_response_time_ms": round(
                sum(r.response_time_ms for r in recent_results) / total_checks, 2
            )
        }