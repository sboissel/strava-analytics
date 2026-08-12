# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-08-12

### Added

- Base release of the Strava analytics pipeline.
- `StravaClient` for OAuth token refresh, activity pagination, and stream fetches.
- Activity enrichment helpers for HR easy/hard stats, pace bins, CSV merges, and weekly summaries.
- Unit tests for `activity_utils` and `strava` modules.
- GitLab CI test job with coverage reporting and README pipeline/coverage badges.
