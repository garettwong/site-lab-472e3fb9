# Design Notes — Sunny / GoldenWin Maid-Agency Counter-Copy

Created: 2026-07-06 00:51 CST
Live preview route: `#/search`

## Core psychology

The end user is a Hong Kong family/employer on mobile. They are busy, cautious, and often anxious because hiring a domestic helper affects home safety, elderly/child care, money, paperwork, and family routines.

Their mental journey is:

1. “I need home help.”
2. “Can I trust this agency?”
3. “Can I search without wasting time?”
4. “Is this helper profile actually updated?”
5. “What happens after I request an interview?”

The prototype answers those questions in order instead of exposing a database immediately.

## Visual rationale

- Premium family-care / concierge tone, not a cheap database.
- Warm ivory, jade, soft gold and editorial photography create safety and service quality without using gimmicky glass effects.
- The page spends its visual “signature” on the care-compass idea: Need → Match → Interview → Track. This makes the site feel guided and human.
- Database complexity is delayed until after the trust promises and journey strip, so users feel helped before they feel filtered.
- Helper cards show last-updated dates, review status, verified-fit tags, share profile, and interview CTA. These are psychological proof cues, not decoration.
- Copy uses the end user’s language: care need, live profile, request interview, track next steps. It avoids backend/product language.

## Owner/business rationale

Frank’s wife/site owner needs fast mobile search, shareable live helper links, helper self-update forms, staff review, and fewer outdated PDF discrepancies. The prototype makes that business logic visible:

- helper self-update form → staff review → public profile updates automatically;
- live detail page with share link and interview button;
- around-50-helper database concept without overwhelming first-time visitors;
- future CRM/admin path implied, but not forced in the first build.

## What changed from the ugly first demo

- Replaced sidebar/database-first feeling with a mobile-first concierge landing flow.
- Built trust before showing helper cards.
- Used human journey and anxiety reduction as the design logic.
- Preserved the full GoldenWin-like hierarchy in an elegant platform map instead of making it dominate the first screen.
- Kept motion restrained: only simple reveal-on-scroll and hover clarity.

## Commercial/safety notes

- No GoldenWin or Sunny proprietary logo, images, data, code, or real helper records are used.
- Helper profiles are synthetic placeholders.
- Existing image assets in the preview folder are synthetic generated placeholders supplied for this repo.
- This is a static private noindex prototype: no real login, payment, form submission, or backend action.
