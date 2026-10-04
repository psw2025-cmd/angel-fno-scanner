# Agent Lock

An agent must claim this lock before editing any file. Release after push.

## Current Lock

<none>

## Format When Held

**Held by:** <agent id>  
**Since:** <ISO timestamp>  
**Working on:** <one-line description>  
**Files being edited:** <list>  
**Expected duration:** <estimate>  

## History

Append a line every time a lock is released:
- 2026-10-05T05:20:00+05:30 — agy CLI — establish core documentation suite — pending commit
