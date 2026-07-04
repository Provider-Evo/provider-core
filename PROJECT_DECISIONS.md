# Architecture Decision Records (ADR)

This document captures significant architectural decisions in the provider-self project using the ADR format. Each record describes the context, options considered, decision, rationale, and consequences.

---

## ADR-001: aiohttp as the HTTP Framework

**Context**: The project needed a modern, async HTTP framework to handle concurrent requests efficiently while maintaining simplicity and performance.

**Options considered**:
- **Option A** — Use Flask or Django with async wrappers.
- **Option B** — Use aiohttp for native async HTTP handling.

**Decision**: Adopted aiohttp as the HTTP framework for the project.

**Rationale**: aiohttp provides native async/await support, excellent performance for concurrent connections, and a simple API that integrates well with Python's asyncio ecosystem. It supports both client and server functionality, making it ideal for a proxy service.

**Consequences**:
- Enabled high-performance async request handling.
- Required understanding of asyncio patterns and event loop management.
- Provided foundation for WebSocket support and streaming responses.

---

## ADR-002: loguru for Logging

**Context**: The project needed a modern, flexible logging solution that could handle structured logging, multiple outputs, and easy configuration.

**Options considered**:
- **Option A** — Use Python's built-in logging module with custom formatters.
- **Option B** — Use loguru for simplified, feature-rich logging.

**Decision**: Adopted loguru as the logging framework.

**Rationale**: loguru provides zero-configuration logging, automatic context tracking, powerful formatting, and easy rotation/retention policies. It simplifies logging setup while offering advanced features like exception formatting and JSON serialization.

**Consequences**:
- Simplified logging configuration and usage.
- Enabled consistent log formatting across all modules.
- Provided built-in support for log rotation and retention.

---

## ADR-003: echotools as a Separate Shared Infrastructure Package

**Context**: The project needed to share common utilities and infrastructure code across multiple components without creating tight coupling.

**Options considered**:
- **Option A** — Keep utilities within the main project.
- **Option B** — Extract shared infrastructure into a separate package (echotools).

**Decision**: Created echotools as a separate shared infrastructure package.

**Rationale**: Separating infrastructure code promotes reusability, reduces duplication, and allows independent versioning and testing. It creates clear boundaries between application logic and infrastructure concerns.

**Consequences**:
- Enabled code reuse across multiple projects.
- Required version management and dependency tracking.
- Promoted cleaner architecture with separation of concerns.

---

## ADR-004: Platform Adapter Pattern

**Context**: The system needed to support multiple LLM providers with different APIs, authentication methods, and response formats.

**Options considered**:
- **Option A** — Implement provider-specific code throughout the codebase.
- **Option B** — Use an adapter pattern to abstract provider differences.

**Decision**: Implemented platform adapter pattern with consistent interfaces.

**Rationale**: The adapter pattern provides a uniform interface while encapsulating provider-specific logic. It enables easy addition of new providers and simplifies maintenance by isolating changes to individual adapters.

**Consequences**:
- Simplified addition of new LLM providers.
- Reduced code duplication across provider implementations.
- Enabled consistent error handling and logging across providers.

---

## ADR-005: pydantic for Configuration and Request Validation

**Context**: The system needed robust configuration management and request validation to ensure data integrity and prevent runtime errors.

**Options considered**:
- **Option A** — Use manual validation with dictionaries and custom validators.
- **Option B** — Use pydantic for automatic validation and settings management.

**Decision**: Adopted pydantic for configuration and request validation.

**Rationale**: pydantic provides automatic data validation, serialization, and settings management through Python type hints. It reduces boilerplate code, catches errors early, and generates clear validation messages.

**Consequences**:
- Reduced validation code and improved type safety.
- Enabled automatic API documentation generation.
- Provided clear error messages for configuration and validation issues.

---

## ADR-006: echotools Optional Runtime Dependencies

**Context**: The project needed to manage optional features and their dependencies without requiring all users to install unnecessary packages.

**Options considered**:
- **Option A** — Include all dependencies as required.
- **Option B** — Make platform-specific dependencies optional.

**Decision**: Implemented optional runtime dependencies through echotools.

**Rationale**: Optional dependencies reduce installation footprint for users who don't need specific platform support. It allows the core package to remain lightweight while providing extensibility through optional plugins.

**Consequences**:
- Reduced default installation size and dependencies.
- Required graceful handling of missing optional dependencies.
- Enabled platform-specific features to be installed as needed.

---

## ADR-007: wasmtime for DeepSeek Proof-of-Work

**Context**: The DeepSeek platform required proof-of-work calculations for authentication, needing a secure and efficient WebAssembly runtime.

**Options considered**:
- **Option A** — Implement proof-of-work in pure Python.
- **Option B** — Use wasmtime for WebAssembly-based proof-of-work.

**Decision**: Adopted wasmtime for DeepSeek proof-of-work calculations.

**Rationale**: wasmtime provides a secure, sandboxed WebAssembly runtime that can execute proof-of-work algorithms efficiently. It isolates potentially untrusted code and provides better performance than pure Python implementations.

**Consequences**:
- Enabled secure execution of proof-of-work algorithms.
- Provided performance benefits over pure Python implementations.
- Added WebAssembly runtime as a dependency for DeepSeek support.

---

## ADR-008: pycryptodome for Qwen Authentication

**Context**: The Qwen platform required cryptographic operations for authentication, needing a reliable and secure cryptography library.

**Options considered**:
- **Option A** — Use Python's built-in cryptography modules.
- **Option B** — Use pycryptodome for comprehensive cryptographic support.

**Decision**: Adopted pycryptodome for Qwen authentication.

**Rationale**: pycryptodome provides a comprehensive set of cryptographic primitives, is well-maintained, and offers better performance than pure Python implementations. It supports the specific algorithms needed for Qwen authentication.

**Consequences**:
- Enabled secure authentication with Qwen platform.
- Provided comprehensive cryptographic capabilities.
- Added pycryptodome as a dependency for Qwen support.

---

## ADR-009: beautifulsoup4 and requests for Ollama

**Context**: The Ollama platform integration needed HTML parsing and HTTP client capabilities for interacting with Ollama servers.

**Options considered**:
- **Option A** — Use lxml and urllib for HTML parsing and HTTP requests.
- **Option B** — Use beautifulsoup4 and requests for simpler, more Pythonic APIs.

**Decision**: Adopted beautifulsoup4 and requests for Ollama integration.

**Rationale**: beautifulsoup4 provides intuitive HTML parsing with multiple parser support, while requests offers a simple, human-friendly HTTP API. Together they simplify Ollama server interaction and response parsing.

**Consequences**:
- Simplified HTML parsing and HTTP interactions with Ollama.
- Provided robust error handling and session management.
- Added beautifulsoup4 and requests as dependencies for Ollama support.

---

## ADR-010: cerebras-cloud-sdk for Cerebras Platform

**Context**: The Cerebras platform required integration with their cloud SDK for accessing AI models and services.

**Options considered**:
- **Option A** — Implement Cerebras API integration from scratch.
- **Option B** — Use the official cerebras-cloud-sdk for integration.

**Decision**: Adopted cerebras-cloud-sdk for Cerebras platform integration.

**Rationale**: Using the official SDK ensures compatibility, receives updates and bug fixes, and reduces maintenance burden. It provides type-safe interfaces and follows Cerebras' recommended patterns.

**Consequences**:
- Simplified Cerebras platform integration.
- Received official support and updates.
- Added cerebras-cloud-sdk as a dependency for Cerebras support.

---

## ADR-011: Core Module Shim Consolidation

**Context**: The core modules had accumulated shims and compatibility layers that increased complexity and maintenance burden.

**Options considered**:
- **Option A** — Keep shims for backward compatibility.
- **Option B** — Consolidate and remove unnecessary shims.

**Decision**: Consolidated core module shims and simplified the public API.

**Rationale**: Removing unnecessary shims reduces code complexity, improves maintainability, and provides a cleaner API surface. It eliminates indirection layers that were no longer needed.

**Consequences**:
- Simplified the core module API.
- Reduced maintenance burden and code complexity.
- Required updates to code that used the old shim interfaces.

---

## ADR-012: fncall Protocol Plugin System via echotools

**Context**: The tool calling system needed to support multiple protocols for different LLM providers, requiring a flexible plugin architecture.

**Options considered**:
- **Option A** — Implement protocol-specific code within the core.
- **Option B** — Create a plugin system via echotools for protocol extensions.

**Decision**: Implemented fncall protocol plugin system through echotools.

**Rationale**: A plugin system enables easy addition of new protocols without modifying core code. It promotes separation of concerns and allows protocols to be developed and maintained independently.

**Consequences**:
- Enabled easy addition of new tool calling protocols.
- Simplified protocol maintenance and updates.
- Required plugin registration and discovery mechanisms.

---

## ADR-013: Runner-Worker Dual-Process Architecture

**Context**: The system needed to handle long-running operations and background tasks without blocking the main request handling.

**Options considered**:
- **Option A** — Use threading for concurrent operations.
- **Option B** — Implement runner-worker dual-process architecture.

**Decision**: Implemented runner-worker dual-process architecture.

**Rationale**: Separate processes provide better isolation, avoid GIL limitations, and enable true parallelism. The runner manages worker processes, providing fault tolerance and resource management.

**Consequences**:
- Enabled true parallelism for CPU-bound tasks.
- Provided better isolation and fault tolerance.
- Added complexity in process management and communication.

---

## ADR-014: WebUI SPA Architecture Refactoring

**Context**: The WebUI was originally served through multiple routes (/docs, /webui) and had a monolithic structure, making it difficult to maintain and extend.

**Options considered**:
- **Option A** — Keep existing multi-route structure with incremental improvements.
- **Option B** — Refactor to a frontend-backend separated Single Page Application (SPA) architecture.

**Decision**: Refactored WebUI to frontend-backend separated SPA architecture, abolishing /docs and /webui routes, with root path directly serving the WebUI.

**Rationale**: SPA architecture provides better user experience, cleaner separation of concerns, and easier development of complex UI features. Static file hot-reload and lazy loading improve performance.

**Consequences**:
- Simplified routing and deployment.
- Enabled advanced features like terminal, file manager, and request inspector.
- Required restructuring of static file organization and middleware.

---

## ADR-015: Tool Calling Protocol Refactoring (5 modes)

**Context**: The tool calling (fncall) system needed to support multiple protocols for different LLM providers, but the implementation was scattered and inconsistent.

**Options considered**:
- **Option A** — Keep protocol-specific code scattered across modules.
- **Option B** — Refactor into 5 protocol modes with modularization and config section restructuring.

**Decision**: Implemented 5 protocol modes (original, bracket, antml, xml, nous) with modularization and config section restructuring.

**Rationale**: Different LLM providers require different tool calling formats. A modular system allows easy addition of new protocols and platform-specific mapping.

**Consequences**:
- Enabled platform-specific protocol selection via fncall_mapping.
- Improved maintainability and testability of protocol code.
- Required careful handling of protocol priority (API request > fncall_mapping > global default).

---

## ADR-016: Per-Request Platform Routing

**Context**: The system needed the ability to route individual requests to specific platforms dynamically, rather than relying solely on global configuration.

**Options considered**:
- **Option A** — Keep global platform routing with limited flexibility.
- **Option B** — Implement per-request platform routing via extra_body.platform parameter.

**Decision**: Added per-request platform routing via extra_body.platform (v2.2.200).

**Rationale**: This allows fine-grained control over request routing, enabling A/B testing, gradual rollouts, and platform-specific optimizations without global configuration changes.

**Consequences**:
- Increased flexibility for request routing.
- Required careful handling of platform selection priority.
- Enhanced debugging capabilities with platform visibility in logs.

---

## ADR-017: OpenCode Platform Proxy Pool Strategy

**Context**: The OpenCode platform needed to handle high-volume requests with reliability and performance, requiring intelligent proxy management.

**Options considered**:
- **Option A** — Simple retry logic without proxy rotation.
- **Option B** — Implement proxy-pool based request routing with TAS (Traffic Assignment System) scoring.

**Decision**: Implemented proxy-pool based request routing with single candidate model and internal TAS proxy selection, including retry with proxy rotation on connection errors and rate limits.

**Rationale**: Proxy pool distribution improves reliability and performance by distributing load across multiple proxies. TAS scoring ensures optimal proxy selection based on performance metrics.

**Consequences**:
- Improved request success rate and latency.
- Added complexity in proxy management and scoring.
- Required MAX_RETRIES tuning (reduced from 50 to 3) for optimal performance.

---

## ADR-018: Qwen Platform Core Refactoring

**Context**: The Qwen platform module had accumulated technical debt, with login logic, error handling, and module structure needing simplification.

**Options considered**:
- **Option A** — Incremental fixes within existing structure.
- **Option B** — Major refactoring of qwen/core modules with login logic rewrite and module decomposition.

**Decision**: Major simplification of qwen/core modules, including login logic rewrite to unified polling architecture, module decomposition, and logging migration to loguru.

**Rationale**: The existing structure was complex and hard to maintain. Simplification improves reliability, reduces login failure issues, and enhances logging consistency.

**Consequences**:
- Improved login reliability with queue re-login log aggregation.
- Better error handling with network circuit breaker.
- Cleaner module structure for future extensions.

---

## ADR-019: Auto-Update System with Mirror Sources

**Context**: The project needed a reliable auto-update mechanism that could handle network issues and provide fallback options.

**Options considered**:
- **Option A** — Simple direct update from primary source.
- **Option B** — Implement auto-update with mirror sources, differential updates, and local change auto-stash recovery.

**Decision**: Implemented auto-update system with mirror sources, differential updates, and local change auto-stash recovery.

**Rationale**: Mirror sources provide redundancy and reliability. Differential updates reduce bandwidth usage. Auto-stash recovery prevents data loss during updates.

**Consequences**:
- Improved update reliability and user experience.
- Added complexity in mirror source management and priority configuration.
- Enhanced user control with diff preview and auto hot-reload.

---

## ADR-020: Browser-Based Cookie Authentication

**Context**: The system needed secure authentication for browser-based access while maintaining simplicity for API clients.

**Options considered**:
- **Option A** — Token-based authentication for all clients.
- **Option B** — Browser-based Cookie authentication with static resource bypass.

**Decision**: Implemented browser login page with Cookie authentication and static resource bypass.

**Rationale**: Cookie authentication provides seamless browser experience while static resource bypass improves performance. API clients can continue using token-based auth.

**Consequences**:
- Enhanced security for browser-based access.
- Required enforcement of authentication on all endpoints (including /health and /v1/models).
- Improved user experience with login page and session management.

---

## ADR-021: File Manager and Terminal Features

**Context**: The WebUI needed advanced development tools to improve developer productivity and provide a complete development environment.

**Options considered**:
- **Option A** — Basic file viewing and command execution.
- **Option B** — Full-featured file manager with editing, upload, copy/move, search, and terminal with session persistence.

**Decision**: Implemented comprehensive file manager with editing, upload, copy/move, search, cross-module linkage, and terminal with session persistence, ConPTY upgrade, and Windows compatibility.

**Rationale**: These features transform the WebUI into a complete development environment, reducing context switching and improving developer workflow.

**Consequences**:
- Significantly enhanced WebUI functionality.
- Required careful handling of security and permissions.
- Added complexity in terminal implementation across platforms.

---

## ADR-022: Request Inspector and Batch Testing

**Context**: Developers needed tools to inspect API requests and test endpoints efficiently, especially for debugging and validation.

**Options considered**:
- **Option A** — External tools for request inspection and testing.
- **Option B** — Integrated request inspector with real-time streaming and batch testing capabilities.

**Decision**: Implemented request inspector with real-time streaming content broadcast, raw request display, and batch testing with OpenAI Batch style, statistics, and streaming capture.

**Rationale**: Integrated tools provide seamless developer experience, reduce context switching, and enable efficient debugging and testing workflows.

**Consequences**:
- Improved debugging capabilities and developer productivity.
- Added complexity in real-time streaming and data persistence.
- Enhanced reporting with statistics and detailed results.

---

Generated on: 2026-07-02

---

## ADR-023: DSML Tool-Calling Protocol Addition

**Context**: The tool calling (fncall) system needed to support the DSML protocol for specific LLM providers that use a different tool invocation format, requiring extension of the existing 5-protocol architecture.

**Options considered**:
- **Option A** — Extend existing bracket/antml protocols to accommodate DSML format.
- **Option B** — Add DSML as a new standalone protocol mode alongside existing ones.

**Decision**: Added DSML as a 6th protocol mode with dedicated parser and renderer (v2.2.192).

**Rationale**: DSML has a distinct syntax and semantics that cannot be cleanly mapped to existing protocols without significant complexity. A standalone protocol keeps each implementation focused and maintainable.

**Consequences**:
- Increased protocol count from 5 to 6, expanding fncall_mapping options.
- Required new protocol-specific tests and documentation.
- Maintained backward compatibility with existing protocol configurations.

---

## ADR-024: native_tools Platform Capability Declaration

**Context**: Some LLM platforms natively support tool calling in their API, bypassing the need for fncall protocol rendering. The system needed a way for platforms to declare this capability.

**Options considered**:
- **Option A** — Keep tool calling always routed through the fncall plugin system.
- **Option B** — Allow platforms to declare native tool calling support, bypassing fncall.

**Decision**: Added `native_tools` capability flag that platforms can set to indicate native tool calling support, allowing the gateway to skip fncall processing for those platforms.

**Rationale**: For platforms that natively support tool calling, forcing requests through the fncall protocol layer adds unnecessary complexity and can degrade tool calling quality. Native support is simpler and more reliable.

**Consequences**:
- Platforms can now opt out of fncall processing.
- Gateway routing logic became more complex with capability-based branching.
- Required careful handling of the transition path for platforms that partially support native tools.

---

## ADR-025: ProxySelector Smart Proxy Selection

**Context**: The system needed intelligent proxy selection across multiple proxy sources, replacing the previous static candidate model with dynamic scoring-based selection.

**Options considered**:
- **Option A** — Continue using static candidate lists with round-robin selection.
- **Option B** — Implement a ProxySelector with dynamic scoring and performance-based selection.

**Decision**: Implemented ProxySelector that evaluates proxies based on latency, success rate, and availability, selecting the optimal proxy for each request.

**Rationale**: Static proxy selection does not account for real-time proxy performance. Dynamic selection based on actual metrics improves request success rate and reduces latency.

**Consequences**:
- Improved request routing based on real-time proxy performance.
- Added scoring overhead per request, though minimal.
- Required proxy metric collection and persistence infrastructure.

---

## ADR-026: 5-Dimensional Adaptive TAS Scoring

**Context**: The OpenCode platform's Traffic Assignment System (TAS) used simple scoring that did not adequately capture proxy performance across multiple dimensions.

**Options considered**:
- **Option A** — Keep the existing simple scoring model.
- **Option B** — Refactor to a 5-dimensional adaptive scoring system with persistence.

**Decision**: Refactored TAS to use 5 scoring dimensions (latency, success rate, error rate, availability, throughput) with adaptive weighting and persistent score storage.

**Rationale**: A multi-dimensional scoring model provides a more accurate proxy quality assessment. Adaptive weighting allows the system to adjust to changing conditions, and persistence prevents score loss on restart.

**Consequences**:
- Improved proxy selection accuracy and request success rate.
- Added complexity in scoring calculation and weight management.
- Score persistence required storage infrastructure and periodic refresh logic.

---

## ADR-027: Platform Compliance Audit and Standardization

**Context**: Platform adapters had accumulated inconsistencies in naming conventions, interface patterns, and code organization, making maintenance and extension difficult.

**Options considered**:
- **Option A** — Keep existing platform interfaces with incremental fixes.
- **Option B** — Conduct a full compliance audit with standardized naming and patterns.

**Decision**: Conducted a platform-wide compliance audit, renaming internal modules (impl to adaptercore), extracting constants, and standardizing facade patterns.

**Rationale**: Consistent patterns across platform adapters reduce cognitive load for developers, make the codebase more predictable, and simplify adding new platforms.

**Consequences**:
- Improved code consistency across all platform adapters.
- Required updates to all platform import paths.
- Established a reference pattern for future platform implementations.

---

## ADR-028: Platform-Specific Config Sub-sections

**Context**: Platform configuration was limited to top-level settings, making it difficult to configure platform-specific options like base_url without polluting the global namespace.

**Options considered**:
- **Option A** — Keep all platform config at the top level of config.toml.
- **Option B** — Introduce `[platforms.<name>]` sub-sections for platform-specific settings.

**Decision**: Added `[platforms.<name>]` config sub-sections to expose platform-specific settings like base_url while keeping the global config clean.

**Rationale**: Platform-specific settings logically belong to their respective platforms. Sub-sections provide clear organization and prevent naming conflicts between platforms.

**Consequences**:
- Cleaner config.toml structure with better separation of concerns.
- Required config migration for existing platform-specific settings.
- Enabled per-platform base_url configuration without global overrides.

---

## ADR-029: Qwen Network Circuit Breaker

**Context**: Qwen platform login operations were failing silently under network instability, causing cascading failures and poor user experience.

**Options considered**:
- **Option A** — Keep simple retry logic with exponential backoff.
- **Option B** — Implement a network circuit breaker that stops attempts after repeated failures and periodically tests recovery.

**Decision**: Implemented a network circuit breaker for Qwen login operations with failure counting, open/closed/half-open states, and automatic recovery probing.

**Rationale**: A circuit breaker prevents wasted resources on doomed requests and provides faster recovery detection than simple retries. It isolates network issues from application logic.

**Consequences**:
- Reduced resource waste during network outages.
- Improved login reliability with automatic recovery detection.
- Added complexity in circuit breaker state management and configuration.

---

## ADR-030: Qwen Periodic Token Validation and Auto-Relogin

**Context**: Qwen session tokens expired silently, causing request failures that were not caught until actual API calls were made.

**Options considered**:
- **Option A** — Rely on API error responses to trigger token refresh.
- **Option B** — Implement periodic background token validation with proactive relogin.

**Decision**: Added a background task that periodically validates Qwen tokens and triggers automatic relogin when tokens are detected as invalid.

**Rationale**: Proactive token validation prevents user-facing errors by refreshing tokens before they expire. Background validation is invisible to users and maintains session continuity.

**Consequences**:
- Reduced token expiration-related request failures.
- Added background task management and scheduling complexity.
- Required careful interval tuning to balance freshness vs API call overhead.

---

## ADR-031: Future Annotations Adoption

**Context**: The codebase was inconsistent in using Python type hints, with some modules using string annotations and others using direct type references, causing potential circular import issues.

**Options considered**:
- **Option A** — Keep the existing mixed annotation style.
- **Option B** — Adopt `from __future__ import annotations` across all core and platform modules.

**Decision**: Adopted `from __future__ import annotations` in core and Qwen modules to enable PEP 563 postponed evaluation of annotations.

**Rationale**: Future annotations prevent circular import issues, enable forward references, and allow cleaner type hint syntax. They also improve runtime performance by avoiding annotation evaluation at import time.

**Consequences**:
- Eliminated potential circular import issues in type hints.
- Enabled cleaner type hint syntax with forward references.
- Required validation that runtime annotation inspection still works where needed.

---

## ADR-032: echotools.web Shared Web Logic Extraction

**Context**: Common web-related utilities (static file serving, middleware, WebSocket helpers) were duplicated across the provider-self project and other projects using echotools.

**Options considered**:
- **Option A** — Keep web utilities within each project.
- **Option B** — Extract common web logic into echotools.web as a shared module.

**Decision**: Extracted common web-related utilities into `echotools.web` as a shared module, reducing duplication across projects.

**Rationale**: Web utilities like static file middleware, WebSocket helpers, and request processing patterns are common across projects. Centralizing them in echotools.web promotes reuse and consistency.

**Consequences**:
- Reduced code duplication for web utilities across projects.
- Required version coordination between provider-self and echotools.
- Established echotools.web as the standard location for shared web logic.

---

## ADR-033: Terminal System Migration to T3 Code Architecture

**Context**: The existing terminal system in provider-v2 had limited functionality compared to T3 Code's implementation. T3 Code provided a more complete terminal experience with shell fallback chains, output sanitization, subprocess monitoring, history management, and multi-client support.

**Options considered**:
- **Option A** — Keep existing terminal implementation and add features incrementally.
- **Option B** — Migrate to T3 Code's architecture while maintaining backward compatibility.

**Decision**: Migrated provider-v2's terminal system to match T3 Code's architecture, updating both echotools and provider-v2 while keeping existing WebUI functional.

**Rationale**: T3 Code's terminal implementation provided a more robust and feature-complete solution with:
1. Shell fallback chains for cross-platform compatibility
2. Output sanitization for clean history management
3. Subprocess monitoring with metadata events
4. History management with 5000-line limit
5. Multi-client support with process keep-alive
6. Clear and restart operations

**Consequences**:
- Enhanced terminal functionality with clear history, restart, and subprocess monitoring.
- Improved cross-platform compatibility with shell fallback chains.
- Added metadata events for real-time subprocess status updates.
- Maintained backward compatibility with existing WebUI.
- Required version coordination between echotools and provider-v2.
- Established pattern for future terminal feature development.

---

## ADR-034: Runner-MainWorker-WebUIWorker Triple-Process Architecture

**Context**: The existing Runner-Worker dual-process architecture had all functionality (API handling, WebUI, file watching) in a single Worker process. This created coupling between API and WebUI components, making it difficult to restart or update them independently.

**Options considered**:
- **Option A** — Keep existing dual-process architecture with incremental improvements.
- **Option B** — Refactor to triple-process architecture with separate MainWorker (API) and WebUIWorker (WebUI).

**Decision**: Refactored to Runner-MainWorker-WebUIWorker triple-process architecture (v2.2.239).

**Rationale**: Separating API and WebUI into independent processes provides:
1. Independent lifecycle management — WebUI crashes don't affect API service
2. Better fault isolation — API restarts don't require WebUI restart
3. Clear separation of concerns — API and WebUI have different restart triggers
4. Shared memory communication for Registry synchronization
5. Enhanced startup_force_kill_port logic to handle both ports (1337 and 8001)

**Consequences**:
- Runner now manages two child processes instead of one.
- Exit code protocol extended: 42 (MainWorker restart), 43 (WebUIWorker restart), 44 (both restart).
- New WORKER_TYPE environment variable distinguishes MainWorker vs WebUIWorker.
- FileWatcher behavior varies by worker type — MainWorker triggers restart, WebUIWorker only logs.
- Added webui_port configuration option (default 8001).
- Increased process management complexity but improved system resilience.
- Required shared memory module (src/core/ipc/) for cross-process data sharing.