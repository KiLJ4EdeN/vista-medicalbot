# Manual Testing Guide - Swagger UI

Open `http://localhost:8000/docs` in your browser.

---

## Auth Flow

1. **POST /auth/register** - fill `email`, `full_name`, `password` and copy `token`
2. **POST /auth/login** - fill `email`, `password`; it returns the same permanent token
3. Click **Authorize** (top right), paste `token`, and authenticate user endpoints

---

## Standard User Flow (authenticated)

4. **GET /profile** - view your user details
5. **PATCH /profile** - update name/email
6. **POST /profile/password** - change password without changing the token
7. **POST /sessions** - create a session and copy `id`
8. **GET /sessions** - list sessions
9. **PATCH /sessions/{session_id}** - rename
10. **POST /uploads/sessions/{session_id}** - upload a PDF/JPEG/PNG/WebP and copy `id`
11. **GET /uploads/sessions/{session_id}** - list session files
12. **POST /uploads/{upload_id}/download** - get presigned download URL
13. **DELETE /uploads/{upload_id}** - delete upload
14. **POST /sessions/{session_id}/messages** - send `content` and optional session-scoped `upload_ids`; receive SSE lifecycle, tool, and final-answer events
15. **GET /sessions/{session_id}/messages** - view ordered history with attachment metadata and presigned URLs for referenced uploads
16. **POST /stt** - upload audio for transcription
17. **DELETE /sessions/{session_id}** - permanently delete the session, messages, and uploaded files

---

## Admin Flow

Set `x-api-key` header in Swagger UI for these endpoints (click Authorize → enter your admin API key).

18. **GET /admin/stats** - dashboard metrics
19. **GET /admin/users** - list all users
20. **POST /admin/users/{user_id}/activate** - enable user and their permanent token
21. **POST /admin/users/{user_id}/deactivate** - block user and token access
22. **POST /knowledge** - upload a knowledge document for background processing
23. **GET /knowledge** - list entries
24. **PATCH /knowledge/{entry_id}** - update metadata and trigger reprocessing
25. **POST /knowledge/search/test** - test hybrid search
26. **POST /knowledge/{entry_id}/download** - get a presigned download URL
27. **POST /knowledge/{entry_id}/reindex** - reprocess from scratch
28. **DELETE /knowledge/{entry_id}** - permanently delete the entry, source file, and vectors
