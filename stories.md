# Future Enhancements and Backlog

## Overlay Injection Optimization

**Story:** Only inject overlays/highlights if they aren’t already present

**Context:**
- Repeated overlay injection during DOM scans causes page flicker and DOM bloat.
- Overlays should only be injected if not already present on a target element.
- This will improve stability, performance, and user experience.

**Acceptance Criteria:**
- Overlay injection logic checks for presence (by class or data attribute) before adding overlays.
- No duplicate overlays are created on repeated scans.
- Debug logging is added for overlay injection/skipping.
- No flicker or DOM bloat on repeated scans.

**References:**
- See buildDomTree.js and DOMService overlay/highlight logic.

---

Add further details or acceptance criteria as needed when this story is prioritized.
